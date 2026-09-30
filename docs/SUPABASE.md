# EdgeSecurity — Supabase/PostgreSQL Configuration

## Visão Geral

O EdgeSecurity migrou de SQLite para PostgreSQL (Supabase) como banco de dados persistente principal. O código suporta **ambos** os backends simultaneamente:

- **Desenvolvimento local**: SQLite (padrão, zero config)
- **Produção**: PostgreSQL via Supabase

---

## 1. Criar Projeto no Supabase

1. Acesse https://supabase.com/dashboard
2. Clique em **New Project**
3. Escolha organização, nome do projeto (ex: `edgesecurity`), senha do banco, região
4. Aguarde provisionamento (~2 min)

---

## 2. Obter Credenciais

### Database URL (Connection String)

Dashboard → **Settings** → **Database** → **Connection string** → **URI**

```
postgresql://postgres:[SUA_SENHA]@db.[PROJECT_REF].supabase.co:5432/postgres
```

Substitua `[SUA_SENHA]` pela senha definida no passo 1.

### API Keys (para futuras integrações)

Dashboard → **Settings** → **API**

- **Project URL**: `https://[PROJECT_REF].supabase.co`
- **anon/public key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (pode expor no frontend)
- **service_role key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` **NUNCA exponha no frontend**

---

## 3. Configurar Variáveis de Ambiente

### Backend (`.env` na raiz ou `backend/.env`)

```bash
# PostgreSQL/Supabase
DATABASE_URL=postgresql://postgres:SUA_SENHA@db.xxx.supabase.co:5432/postgres
# ou
SUPABASE_DB_URL=postgresql://postgres:SUA_SENHA@db.xxx.supabase.co:5432/postgres

# Supabase (para Auth/Storage futuro)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # APENAS BACKEND

# Opcional: pool tuning
PG_POOL_MIN=2
PG_POOL_MAX=10
```

### Frontend (Vercel Environment Variables)

```bash
# Apenas se usar Supabase Auth/Storage no futuro
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

---

## 4. Executar Migrations

As migrations estão em `migrations/` e devem ser executadas **em ordem** no SQL Editor do Supabase:

### Migration 001 — Schema Inicial
```sql
-- Copie e cole o conteúdo de migrations/001_initial_schema.sql
-- Cria todas as tabelas, índices, triggers, RLS
```

### Migration 002 — Super Admin & Funções
```sql
-- Copie e cole o conteúdo de migrations/002_super_admin_and_seed.sql
-- Cria super_admin, funções auxiliares
```

> **Importante**: Execute uma por vez, aguarde sucesso antes da próxima.

---

## 5. Verificar Instalação

No SQL Editor do Supabase:

```sql
-- Verificar tabelas
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Verificar super_admin
SELECT id, nome, email, cargo FROM usuarios WHERE cargo = 'super_admin';

-- Verificar RLS habilitado
SELECT tablename, rowsecurity FROM pg_tables 
WHERE schemaname = 'public' AND rowsecurity = true;
```

---

## 6. Row Level Security (RLS)

O schema habilita RLS em todas as tabelas multi-tenant. As **políticas** serão adicionadas quando integrarmos Supabase Auth (fase futura).

**Atualmente**: Isolamento feito na **camada de aplicação** via `company_id` em todas as queries (mantém comportamento atual).

---

## 7. Testar Localmente com Supabase

```bash
# 1. Instalar dependências
cd backend
pip install -r requirements.txt

# 2. Configurar .env com DATABASE_URL do Supabase
cp .env.example .env
# edite .env

# 3. Rodar backend
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000

# 4. Verificar logs
# Deve aparecer: "Database backend: postgresql"
#                 "Using PostgreSQL/Supabase"
```

---

## 8. Deploy na Vercel (Backend Serverless)

O `api/index.py` já configura `DATABASE_URL` para `/tmp/edgesecurity.db` (SQLite em memória). Para usar PostgreSQL real na Vercel:

1. Adicione `DATABASE_URL` nas **Environment Variables** do projeto Vercel
2. O `api/index.py` detecta automaticamente e usa PostgreSQL
3. **Atenção**: Serverless functions têm limite de conexões. Use `PG_POOL_MIN=1`, `PG_POOL_MAX=3`

---

## 9. Troubleshooting

| Erro | Causa | Solução |
|------|-------|---------|
| `psycopg not installed` | Dependência faltando | `pip install psycopg[pool]` |
| `connection refused` | IP não permitido | Supabase → Settings → Database → Allow all IPs (0.0.0.0/0) |
| `password authentication failed` | Senha errada | Verifique DATABASE_URL, senha do banco |
| `too many connections` | Pool esgotado | Reduza `PG_POOL_MAX`, aumente timeout |
| `relation does not exist` | Migration não rodou | Execute migrations 001 e 002 no SQL Editor |

---

## 10. Estrutura de Arquivos

```
EdgeSecurity/
├── migrations/
│   ├── 001_initial_schema.sql    # Schema completo + RLS
│   └── 002_super_admin_and_seed.sql  # Super admin + funções
├── backend/
│   ├── database.py               # Camada unificada SQLite/PostgreSQL
│   ├── app.py                    # FastAPI app (usa database.py)
│   └── requirements.txt          # + psycopg[pool], asyncpg
├── .env.example                  # Template com todas as variáveis
└── api/
    └── index.py                  # Vercel serverless entry (auto-detecta DB)
```

---

## 11. Próximos Passos (Roadmap)

1. ✅ Schema + migrations
2. ✅ Camada de banco unificada
3. 🔄 Correção sessão/auth (FASE 3)
4. 🔄 Validação IA local (FASE 4)
5. 🔄 Integração alertas → Supabase (FASE 5)
6. 🔄 Benchmark multi-câmera (FASE 6)
7. 🔄 Supabase Auth (opcional, fase futura)
8. 🔄 Supabase Storage para modelos (opcional)

---

## 12. Rollback para SQLite

Se precisar voltar temporariamente:

```bash
# Remova DATABASE_URL do .env
unset DATABASE_URL
# ou comente no .env
# DATABASE_URL=...

# Reinicie backend
# Logs mostrarão: "Database backend: sqlite"
```