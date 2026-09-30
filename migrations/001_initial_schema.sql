-- EdgeSecurity PostgreSQL Migration 001
-- Initial schema matching current SQLite structure
-- Run this on Supabase PostgreSQL

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- CORE TABLES
-- =============================================

CREATE TABLE companies (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    razao_social TEXT NOT NULL,
    nome_fantasia TEXT NOT NULL,
    cnpj TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    telefone TEXT,
    endereco TEXT,
    cidade TEXT,
    estado TEXT,
    status TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa','bloqueada','pendente')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usuarios (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    cargo TEXT NOT NULL CHECK (cargo IN ('administrador','usuario','super_admin')),
    status TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo','bloqueado')),
    ultimo_login TIMESTAMPTZ,
    ultimo_logout TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tempo_total_ativo BIGINT NOT NULL DEFAULT 0,
    administrador_primario BOOLEAN NOT NULL DEFAULT FALSE,
    company_id TEXT REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE permissoes (
    usuario_id TEXT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    visualizar_cameras BOOLEAN NOT NULL DEFAULT TRUE,
    usar_camera_dispositivo BOOLEAN NOT NULL DEFAULT TRUE,
    gerenciar_cameras BOOLEAN NOT NULL DEFAULT FALSE,
    visualizar_alertas BOOLEAN NOT NULL DEFAULT TRUE,
    visualizar_relatorios BOOLEAN NOT NULL DEFAULT TRUE,
    gerenciar_usuarios BOOLEAN NOT NULL DEFAULT FALSE,
    gerenciar_permissoes BOOLEAN NOT NULL DEFAULT FALSE,
    acessar_configuracoes BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE cameras (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('browser','ip','rtsp','wifi')),
    device_id TEXT,
    endereco TEXT,
    localizacao TEXT,
    status TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo','offline','erro')),
    ultima_verificacao TIMESTAMPTZ,
    ultimo_online TIMESTAMPTZ,
    ultimo_erro TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    company_id TEXT REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE usuario_cameras (
    usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    PRIMARY KEY (usuario_id, camera_id)
);

CREATE TABLE alertas (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    camera_id TEXT REFERENCES cameras(id) ON DELETE SET NULL,
    tipo TEXT NOT NULL,
    nivel TEXT NOT NULL,
    descricao TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Aberto' CHECK (status IN ('Aberto','Em Andamento','Resolvido','Ignorado')),
    data_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL
);

CREATE TABLE atividades (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    usuario_id TEXT REFERENCES usuarios(id) ON DELETE SET NULL,
    acao TEXT NOT NULL,
    descricao TEXT NOT NULL,
    data_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL
);

CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pendente','ativa','atrasada','cancelada','bloqueada')),
    valor NUMERIC(10,2) NOT NULL,
    data_inicio TIMESTAMPTZ,
    data_vencimento TIMESTAMPTZ,
    ultimo_pagamento TIMESTAMPTZ,
    proximo_vencimento TIMESTAMPTZ,
    transacao_id TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE payments (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    valor NUMERIC(10,2) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pendente','pago','recusado','cancelado')),
    data_cobranca TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_pagamento TIMESTAMPTZ,
    transacao_id TEXT,
    metodo TEXT,
    gateway_payload TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sessoes (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(16), 'hex'),
    usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    inicio TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fim TIMESTAMPTZ,
    duracao_segundos BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'online' CHECK (status IN ('online','offline'))
);

CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(12), 'hex'),
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
    usuario_id TEXT REFERENCES usuarios(id) ON DELETE SET NULL,
    acao TEXT NOT NULL,
    descricao TEXT NOT NULL,
    ip TEXT,
    resultado TEXT NOT NULL DEFAULT 'ok',
    data_hora TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- INDEXES
-- =============================================

CREATE INDEX idx_sessoes_usuario ON sessoes(usuario_id);
CREATE INDEX idx_sessoes_status ON sessoes(status);
CREATE INDEX idx_alertas_data ON alertas(data_hora DESC);
CREATE INDEX idx_atividades_data ON atividades(data_hora DESC);
CREATE INDEX idx_cameras_company ON cameras(company_id);
CREATE INDEX idx_alertas_company ON alertas(company_id);
CREATE INDEX idx_atividades_company ON atividades(company_id);
CREATE INDEX idx_usuarios_company ON usuarios(company_id);
CREATE INDEX idx_subscriptions_company ON subscriptions(company_id);
CREATE INDEX idx_payments_company ON payments(company_id);

-- =============================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================

CREATE OR REPLACE FUNCTION update_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_companies_atualizado
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_atualizado_em();

CREATE TRIGGER trigger_subscriptions_atualizado
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_atualizado_em();

-- =============================================
-- ROW LEVEL SECURITY (RLS) - ENABLE FOR MULTI-TENANT ISOLATION
-- =============================================

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE permissoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuario_cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE alertas ENABLE ROW LEVEL SECURITY;
ALTER TABLE atividades ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Policies will be created after auth integration
-- For now, we rely on application-level filtering via company_id

-- =============================================
-- HELPER FUNCTIONS
-- =============================================

-- Generate random hex ID (matches current Python secrets.token_hex)
CREATE OR REPLACE FUNCTION gen_random_id(bytes INT DEFAULT 12)
RETURNS TEXT AS $$
    SELECT encode(gen_random_bytes(bytes), 'hex');
$$ LANGUAGE sql VOLATILE;

-- Password hashing helper (PBKDF2-SHA256 120k rounds - matches Python)
-- Note: Actual hashing happens in application layer (Python)
-- This is for reference/migration only