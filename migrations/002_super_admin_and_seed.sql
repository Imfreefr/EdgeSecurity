-- EdgeSecurity PostgreSQL Migration 002
-- Super admin creation and default data
-- Run after 001_initial_schema.sql

-- =============================================
-- SUPER ADMIN USER
-- =============================================
-- Password hash will be set via environment variable SUPER_ADMIN_PASSWORD
-- Application layer handles password hashing (PBKDF2-SHA256 120k rounds)
-- This migration only creates the user record if not exists

DO $$
DECLARE
    v_super_admin_email TEXT := 'admin@edgesecurity.com';
    v_super_admin_name TEXT := 'Administrador Master';
    v_super_admin_password_hash TEXT := 'PLACEHOLDER_REPLACE_VIA_APP'; -- Will be set by app on first run
    v_uid TEXT;
BEGIN
    -- Check if super_admin already exists
    IF NOT EXISTS (SELECT 1 FROM usuarios WHERE cargo = 'super_admin' LIMIT 1) THEN
        IF NOT EXISTS (SELECT 1 FROM usuarios WHERE lower(email) = lower(v_super_admin_email)) THEN
            v_uid := gen_random_id(12);
            INSERT INTO usuarios (
                id, nome, email, senha_hash, cargo, status, criado_em,
                administrador_primario, company_id
            ) VALUES (
                v_uid, v_super_admin_name, v_super_admin_email,
                v_super_admin_password_hash, 'super_admin', 'ativo', NOW(),
                FALSE, NULL
            );
            
            INSERT INTO permissoes (
                usuario_id,
                visualizar_cameras, usar_camera_dispositivo, gerenciar_cameras,
                visualizar_alertas, visualizar_relatorios, gerenciar_usuarios,
                gerenciar_permissoes, acessar_configuracoes
            ) VALUES (
                v_uid, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE
            );
            
            RAISE NOTICE 'Super admin user created with ID: %', v_uid;
            RAISE NOTICE 'IMPORTANT: Update senha_hash via application after first login setup';
        END IF;
    END IF;
END $$;

-- =============================================
-- DEFAULT PERMISSIONS FUNCTION
-- =============================================
-- Mirrors Python default_permissions() function

CREATE OR REPLACE FUNCTION get_default_permissions(p_cargo TEXT)
RETURNS JSONB AS $$
DECLARE
    v_admin BOOLEAN := (p_cargo = 'administrador');
    v_base_perms JSONB := '{
        "visualizar_cameras": true,
        "usar_camera_dispositivo": true,
        "gerenciar_cameras": false,
        "visualizar_alertas": true,
        "visualizar_relatorios": true,
        "gerenciar_usuarios": false,
        "gerenciar_permissoes": false,
        "acessar_configuracoes": true
    }'::JSONB;
BEGIN
    IF v_admin THEN
        RETURN '{
            "visualizar_cameras": true,
            "usar_camera_dispositivo": true,
            "gerenciar_cameras": true,
            "visualizar_alertas": true,
            "visualizar_relatorios": true,
            "gerenciar_usuarios": true,
            "gerenciar_permissoes": true,
            "acessar_configuracoes": true
        }'::JSONB;
    END IF;
    RETURN v_base_perms;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================
-- SUBSCRIPTION STATUS CHECK FUNCTION
-- =============================================
-- Mirrors Python subscription_status() logic

CREATE OR REPLACE FUNCTION check_subscription_status(p_company_id TEXT)
RETURNS TABLE (
    id TEXT,
    status TEXT,
    valor NUMERIC,
    proximo_vencimento TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.status, s.valor, s.proximo_vencimento
    FROM subscriptions s
    WHERE s.company_id = p_company_id
    ORDER BY s.criado_em DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- =============================================
-- AUTO-UPDATE EXPIRED SUBSCRIPTIONS
-- =============================================
-- Can be run via pg_cron or application startup

CREATE OR REPLACE FUNCTION update_expired_subscriptions()
RETURNS VOID AS $$
BEGIN
    UPDATE subscriptions
    SET status = 'atrasada', atualizado_em = NOW()
    WHERE status = 'ativa'
      AND proximo_vencimento IS NOT NULL
      AND proximo_vencimento < NOW();
    
    UPDATE companies
    SET status = 'bloqueada', atualizado_em = NOW()
    WHERE id IN (
        SELECT company_id FROM subscriptions
        WHERE status = 'atrasada'
    );
END;
$$ LANGUAGE plpgsql VOLATILE;

-- =============================================
-- CLEANUP OFFLINE SESSIONS
-- =============================================
-- Mirrors Python session cleanup logic

CREATE OR REPLACE FUNCTION cleanup_stale_sessions(p_idle_timeout_hours INT DEFAULT 8)
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE sessoes
    SET status = 'offline', fim = NOW()
    WHERE status = 'online'
      AND ultimo_heartbeat < NOW() - (p_idle_timeout_hours || ' hours')::INTERVAL;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql VOLATILE;