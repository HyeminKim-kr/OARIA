-- ============================================================
-- Admin 인증 스키마
-- 승인 기반 Google OAuth 방식
-- ============================================================

-- ============================================================
-- 1. admin_users (관리자)
-- ============================================================
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Google OAuth 정보
    email VARCHAR(255) NOT NULL,
    google_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    picture VARCHAR(512),

    -- 승인 상태
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    role VARCHAR(50) NOT NULL DEFAULT 'admin',      -- super_admin, admin, viewer

    -- 승인 정보
    approved_by UUID REFERENCES admin_users(id),
    approved_at TIMESTAMPTZ,
    rejected_reason TEXT,

    -- 상태
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX ix_admin_users_email ON admin_users(email);
CREATE UNIQUE INDEX ix_admin_users_google_id ON admin_users(google_id);
CREATE INDEX ix_admin_users_status ON admin_users(status);
CREATE INDEX ix_admin_users_role ON admin_users(role);

-- ============================================================
-- 2. admin_refresh_tokens (관리자 JWT Refresh Token)
-- ============================================================
CREATE TABLE admin_refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,

    -- 토큰 정보
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,

    -- 디바이스 정보
    device_info VARCHAR(255),
    ip_address VARCHAR(45),

    -- 폐기 정보
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(100),

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX ix_admin_refresh_tokens_admin_id ON admin_refresh_tokens(admin_id);
CREATE INDEX ix_admin_refresh_tokens_token_hash ON admin_refresh_tokens(token_hash);
CREATE INDEX ix_admin_refresh_tokens_valid ON admin_refresh_tokens(admin_id, expires_at)
    WHERE revoked_at IS NULL;

-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Admin 인증 스키마 초기화 완료!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '테이블:';
    RAISE NOTICE '  - admin_users (승인 기반 관리자)';
    RAISE NOTICE '  - admin_refresh_tokens (JWT 토큰 관리)';
    RAISE NOTICE '========================================';
END $$;
