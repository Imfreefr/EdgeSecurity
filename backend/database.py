"""
EdgeSecurity Database Layer
Supports both SQLite (local dev) and PostgreSQL/Supabase (production)
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional
from time import perf_counter
from perf import current as perf_current, measure

# Optional PostgreSQL support
try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False

# Optional asyncpg support
ASYNCPG_AVAILABLE = False
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except (ImportError, OSError):
    # asyncpg requires C++ build tools on Windows
    pass


class DatabaseConfig:
    """Database configuration from environment"""
    
    def __init__(self):
        # SQLite (local development)
        self.sqlite_path = Path(os.getenv("DB_PATH", "backend/edgesecurity.db"))
        
        # PostgreSQL/Supabase (production)
        self.postgres_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
        self.postgres_pool_min = int(os.getenv("PG_POOL_MIN", "2"))
        self.postgres_pool_max = int(os.getenv("PG_POOL_MAX", "10"))
        
        # Determine active backend
        self.use_postgres = bool(self.postgres_url and PSYCOPG_AVAILABLE)
    
    @property
    def backend_name(self) -> str:
        return "postgresql" if self.use_postgres else "sqlite"


class Database:
    """Unified database interface"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool: Optional[ConnectionPool] = None
        self._async_pool: Optional[asyncpg.Pool] = None
    
    @property
    def param_style(self) -> str:
        """Return parameter placeholder style for current backend"""
        return "%s" if self.config.use_postgres else "?"
    
    def _init_sqlite(self):
        """Initialize SQLite connection"""
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.config.sqlite_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn
    
    def _init_postgres_pool(self) -> ConnectionPool:
        """Initialize PostgreSQL connection pool.

        prepare_threshold=None disables server-side prepared statements,
        required for Supavisor/pgbouncer transaction mode (serverless).
        """
        if not self._pool:
            self._pool = ConnectionPool(
                self.config.postgres_url,
                min_size=self.config.postgres_pool_min,
                max_size=self.config.postgres_pool_max,
                kwargs={"row_factory": dict_row, "prepare_threshold": None,
                        "connect_timeout": 10},
                open=False
            )
            self._pool.open()
            self._pool.wait()
        return self._pool
    
    async def _init_async_pool(self) -> asyncpg.Pool:
        """Initialize async PostgreSQL pool"""
        if not self._async_pool:
            self._async_pool = await asyncpg.create_pool(
                self.config.postgres_url,
                min_size=self.config.postgres_pool_min,
                max_size=self.config.postgres_pool_max,
            )
        return self._async_pool
    
    class _ConnectionWrapper:
        """Wrapper that converts ? to %s for PostgreSQL"""
        def __init__(self, conn, convert_params):
            self._conn = conn
            self._convert = convert_params
        
        def execute(self, query: str, params: tuple = ()):
            query = self._convert(query)
            metrics = perf_current.get()
            if metrics is not None:
                metrics["queries"] = metrics.get("queries", 0) + 1
            with measure("db_ms"):
                return self._conn.execute(query, params)
        
        def executemany(self, query: str, params_list: list):
            query = self._convert(query)
            return self._conn.executemany(query, params_list)
        
        def fetchone(self, query: str, params: tuple = ()):
            query = self._convert(query)
            return self._conn.execute(query, params).fetchone()
        
        def fetchall(self, query: str, params: tuple = ()):
            query = self._convert(query)
            return self._conn.execute(query, params).fetchall()
        
        def fetchval(self, query: str, params: tuple = ()):
            query = self._convert(query)
            return self._conn.execute(query, params).fetchone()[0] if self._conn.execute(query, params).fetchone() else None
        
        def executescript(self, script: str):
            return self._conn.executescript(script)
        
        def commit(self):
            return self._conn.commit()
        
        def rollback(self):
            return self._conn.rollback()
        
        def close(self):
            return self._conn.close()
        
        def __getattr__(self, name):
            return getattr(self._conn, name)
    
    @contextmanager
    def conn(self):
        """Get a database connection (context manager)"""
        if self.config.use_postgres:
            with measure("pool_init_ms"):
                pool = self._init_postgres_pool()
            checkout = perf_counter()
            with pool.connection() as conn:
                metrics = perf_current.get()
                if metrics is not None:
                    metrics["acquire_ms"] = metrics.get("acquire_ms", 0) + (perf_counter() - checkout) * 1000
                    metrics["connections"] = metrics.get("connections", 0) + 1
                try:
                    yield self._ConnectionWrapper(conn, self._convert_params)
                    with measure("transaction_ms"):
                        conn.commit()
                except Exception:
                    conn.rollback()
                    raise
        else:
            with measure("acquire_ms"):
                conn = self._init_sqlite()
            metrics = perf_current.get()
            if metrics is not None:
                metrics["connections"] = metrics.get("connections", 0) + 1
            try:
                yield self._ConnectionWrapper(conn, self._convert_params)
                with measure("transaction_ms"):
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    
    async def aconn(self):
        """Get async PostgreSQL connection"""
        if not self.config.use_postgres:
            raise RuntimeError("Async connections only available with PostgreSQL")
        pool = await self._init_async_pool()
        async with pool.acquire() as conn:
            yield conn
    
    def _convert_params(self, query: str) -> str:
        """Convert ? placeholders to %s for PostgreSQL"""
        if self.config.use_postgres:
            return query.replace("?", "%s")
        return query
    
    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query (non-SELECT)"""
        query = self._convert_params(query)
        with self.conn() as conn:
            if self.config.use_postgres:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur
            else:
                return conn.execute(query, params)
    
    def execute_many(self, query: str, params_list: list) -> Any:
        """Execute multiple queries"""
        query = self._convert_params(query)
        with self.conn() as conn:
            if self.config.use_postgres:
                with conn.cursor() as cur:
                    cur.executemany(query, params_list)
                    return cur
            else:
                return conn.executemany(query, params_list)
    
    def fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch single row"""
        query = self._convert_params(query)
        with self.conn() as conn:
            if self.config.use_postgres:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    row = cur.fetchone()
                    return dict(row) if row else None
            else:
                row = conn.execute(query, params).fetchone()
                return dict(row) if row else None
    
    def fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows"""
        query = self._convert_params(query)
        with self.conn() as conn:
            if self.config.use_postgres:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return [dict(row) for row in cur.fetchall()]
            else:
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
    
    def fetchval(self, query: str, params: tuple = ()) -> Any:
        """Fetch single value"""
        query = self._convert_params(query)
        with self.conn() as conn:
            if self.config.use_postgres:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    row = cur.fetchone()
                    return row[0] if row else None
            else:
                row = conn.execute(query, params).fetchone()
                return row[0] if row else None
    
    def executescript(self, script: str):
        """Execute multiple statements"""
        if self.config.use_postgres:
            # Use psycopg's ability to execute multiple statements
            # This handles dollar-quoted strings correctly
            with self.conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(script)
        else:
            with self.conn() as conn:
                conn.executescript(script)
    
    def close(self):
        """Close connection pools"""
        if self._pool:
            self._pool.close()
            self._pool = None
        if self._async_pool:
            import asyncio
            asyncio.run(self._async_pool.close())
            self._async_pool = None


# Global instance
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Get global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def set_db(db: Database):
    """Set global database instance (for testing)"""
    global _db_instance
    _db_instance = db


# Backward compatibility functions
@contextmanager
def conn():
    """Backward compatible connection context manager"""
    db = get_db()
    with db.conn() as c:
        yield c


def execute(query: str, params: tuple = ()):
    return get_db().execute(query, params)


def fetchone(query: str, params: tuple = ()):
    return get_db().fetchone(query, params)


def fetchall(query: str, params: tuple = ()):
    return get_db().fetchall(query, params)


def fetchval(query: str, params: tuple = ()):
    return get_db().fetchval(query, params)
