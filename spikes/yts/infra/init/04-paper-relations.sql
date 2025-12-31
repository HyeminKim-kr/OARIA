-- 04-paper-relations.sql
-- 논문 관계 테이블 및 플래그 컬럼 추가
-- Created: 2026-01-01

-- ============================================================
-- papers 테이블에 새 컬럼 추가
-- ============================================================

-- 논문 유형 배열
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pub_types TEXT[];

-- 정정/철회 플래그
ALTER TABLE papers ADD COLUMN IF NOT EXISTS has_correction BOOLEAN DEFAULT FALSE;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS has_erratum BOOLEAN DEFAULT FALSE;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS has_retraction BOOLEAN DEFAULT FALSE;

-- pub_types 인덱스 (GIN for array)
CREATE INDEX IF NOT EXISTS idx_papers_pub_types ON papers USING GIN(pub_types);

-- 플래그 인덱스 (RAG 방어용 빠른 조회)
CREATE INDEX IF NOT EXISTS idx_papers_has_retraction ON papers(id) WHERE has_retraction = TRUE;
CREATE INDEX IF NOT EXISTS idx_papers_has_erratum ON papers(id) WHERE has_erratum = TRUE;
CREATE INDEX IF NOT EXISTS idx_papers_has_correction ON papers(id) WHERE has_correction = TRUE;

-- ============================================================
-- paper_relations 테이블 생성
-- ============================================================

CREATE TABLE IF NOT EXISTS paper_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_pmid TEXT NOT NULL,      -- Correction/Retraction 문서 PMID
    target_pmid TEXT NOT NULL,      -- 원문 PMID
    relation_type TEXT NOT NULL,    -- 정규화: retraction, erratum, correction, comment
    raw_type TEXT,                  -- 원본 문자열 보존
    reference TEXT,                 -- 참조 문자열
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 유니크 제약 (멱등성 보장)
CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_relations
ON paper_relations(source_pmid, target_pmid, relation_type);

-- 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_paper_relations_target ON paper_relations(target_pmid);
CREATE INDEX IF NOT EXISTS idx_paper_relations_source ON paper_relations(source_pmid);
CREATE INDEX IF NOT EXISTS idx_paper_relations_type ON paper_relations(relation_type);

-- ============================================================
-- 코멘트
-- ============================================================
--
-- relation_type 값:
--   - retraction: 철회 (has_retraction=true)
--   - erratum: 오류정정 (has_erratum=true)
--   - correction: 정정 (has_correction=true)
--   - comment: 코멘트 (플래그 없음, 저장만)
--
-- 사용 예시:
--   1. RAG 검색 후 has_retraction=true인 논문 제외
--   2. has_erratum=true인 논문에 경고 표시
--   3. paper_relations에서 관련 정정 문서 조회
