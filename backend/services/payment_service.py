from __future__ import annotations
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

PAYMENT_MOCK = os.getenv("PAYMENT_MOCK", "true").lower() in ("1", "true", "yes")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_months(base: datetime, months: int = 1) -> datetime:
    return base + timedelta(days=30 * months)


class PaymentService:
    @staticmethod
    def criar_cobranca(db: sqlite3.Connection, company_id: str, subscription_id: str, valor: float) -> dict:
        transacao_id = secrets.token_hex(12)
        pid = secrets.token_hex(12)
        db.execute(
            "INSERT INTO payments(id,company_id,subscription_id,valor,status,data_cobranca,transacao_id,metodo,criado_em) VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, company_id, subscription_id, valor, "pendente", now_iso(), transacao_id, "pix", now_iso()),
        )
        db.execute(
            "UPDATE subscriptions SET transacao_id=?, atualizado_em=? WHERE id=?",
            (transacao_id, now_iso(), subscription_id),
        )
        return {"payment_id": pid, "transacao_id": transacao_id, "valor": valor, "status": "pendente"}

    @staticmethod
    def confirmar_pagamento(db: sqlite3.Connection, transacao_id: str, gateway_payload: str = "") -> dict | None:
        row = db.execute("SELECT * FROM payments WHERE transacao_id=?", (transacao_id,)).fetchone()
        if not row:
            return None
        if row["status"] == "pago":
            return dict(row)
        db.execute(
            "UPDATE payments SET status='pago', data_pagamento=?, gateway_payload=? WHERE id=?",
            (now_iso(), gateway_payload, row["id"]),
        )
        sub = db.execute("SELECT * FROM subscriptions WHERE id=?", (row["subscription_id"],)).fetchone()
        if sub:
            inicio = now_iso()
            venc = add_months(datetime.now(timezone.utc), 1).isoformat()
            db.execute(
                "UPDATE subscriptions SET status='ativa', data_inicio=?, data_vencimento=?, ultimo_pagamento=?, proximo_vencimento=?, atualizado_em=? WHERE id=?",
                (inicio, venc, inicio, venc, now_iso(), sub["id"]),
            )
            db.execute(
                "UPDATE companies SET status='ativa' WHERE id=?",
                (sub["company_id"],),
            )
        return dict(db.execute("SELECT * FROM payments WHERE id=?", (row["id"],)).fetchone())

    @staticmethod
    def marcar_atrasada(db: sqlite3.Connection, subscription_id: str):
        db.execute(
            "UPDATE subscriptions SET status='atrasada', atualizado_em=? WHERE id=? AND status='ativa'",
            (now_iso(), subscription_id),
        )
