-- 05-article-jobs-metadata.sql
-- article_jobs에 메타데이터 컬럼 추가
-- Created: 2026-01-01

-- pub_types와 comment_corrections를 저장하기 위한 JSONB 컬럼
-- 검색 단계에서 수집한 메타데이터를 수집 단계까지 전달

ALTER TABLE article_jobs ADD COLUMN IF NOT EXISTS metadata JSONB;

-- 사용 예시:
-- {
--   "pub_types": ["research-article", "journal-article"],
--   "comment_corrections": [
--     {"id": "12345678", "type": "Erratum for", "source": "MED", "reference": "..."}
--   ]
-- }

COMMENT ON COLUMN article_jobs.metadata IS 'Search API에서 수집한 메타데이터 (pub_types, comment_corrections)';
