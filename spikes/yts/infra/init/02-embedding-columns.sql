-- ============================================================
-- 임베딩 관련 컬럼 추가
-- papers 테이블에 임베딩 상태 추적용 컬럼 추가
-- ============================================================

-- 임베딩 상태 컬럼 추가
ALTER TABLE papers ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20);
-- pending, processing, completed, failed

ALTER TABLE papers ADD COLUMN IF NOT EXISTS embedding_chunk_count INTEGER DEFAULT 0;
-- 생성된 청크 수

ALTER TABLE papers ADD COLUMN IF NOT EXISTS embedding_error TEXT;
-- 실패 시 에러 메시지

ALTER TABLE papers ADD COLUMN IF NOT EXISTS embedding_at TIMESTAMPTZ;
-- 임베딩 완료 시각

-- 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_papers_embedding_status
    ON papers(embedding_status);

CREATE INDEX IF NOT EXISTS idx_papers_embedding_pending
    ON papers(created_at)
    WHERE embedding_status IS NULL OR embedding_status = 'pending';

-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '임베딩 컬럼 추가 완료!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '추가된 컬럼:';
    RAISE NOTICE '  - embedding_status (pending/processing/completed/failed)';
    RAISE NOTICE '  - embedding_chunk_count (청크 수)';
    RAISE NOTICE '  - embedding_error (에러 메시지)';
    RAISE NOTICE '  - embedding_at (완료 시각)';
    RAISE NOTICE '========================================';
END $$;
