-- ============================================================
-- PostgreSQL Extensions 초기화
-- 테이블 생성은 Alembic/TypeORM에서 관리
-- ============================================================

-- pg_trgm: trigram 기반 텍스트 검색 (저자명 fuzzy search 등)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'PostgreSQL Extensions 초기화 완료!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Extensions:';
    RAISE NOTICE '  - pg_trgm (fuzzy text search)';
    RAISE NOTICE '';
    RAISE NOTICE '테이블 생성은 마이그레이션 도구에서 관리:';
    RAISE NOTICE '  - Backend (Alembic): papers, batch, users';
    RAISE NOTICE '  - Admin (TypeORM): admin_users';
    RAISE NOTICE '========================================';
END $$;
