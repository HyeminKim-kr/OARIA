# Likes & Bookmarks 스키마

> **Last Updated**: 2026-01-30
> **Related Tables**: `paper_likes`, `bookmark_collections`, `paper_bookmarks`
> **Modified Tables**: `papers` (like_count 컬럼 추가)

---

## ER 다이어그램

```
users ─────┬──< paper_likes >──────── papers
           │
           ├──< bookmark_collections
           │         │
           └──< paper_bookmarks >──── papers
                     │
                     └── collection_id (FK, nullable)
```

---

## 테이블 정의

### papers (변경)

| 컬럼 | 타입 | 제약 | 기본값 | 설명 |
|------|------|------|--------|------|
| like_count | INTEGER | NOT NULL | 0 | 좋아요 수 캐시 |

### paper_likes

유저-논문 좋아요 관계 테이블. 복합 PK 사용.

| 컬럼 | 타입 | 제약 | 기본값 | 설명 |
|------|------|------|--------|------|
| user_id | UUID | PK, FK(users.id), ON DELETE CASCADE | - | 사용자 ID |
| paper_id | UUID | PK, FK(papers.id), ON DELETE CASCADE | - | 논문 ID |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 좋아요 시각 |

**인덱스**:
- `PRIMARY KEY (user_id, paper_id)`
- `ix_paper_likes_paper_id` ON paper_id
- `ix_paper_likes_user_id` ON user_id

### bookmark_collections

북마크 컬렉션(폴더) 테이블. 유저당 기본 컬렉션 1개 자동 생성.

| 컬럼 | 타입 | 제약 | 기본값 | 설명 |
|------|------|------|--------|------|
| id | UUID | PK | gen_random_uuid() | 컬렉션 ID |
| user_id | UUID | FK(users.id), ON DELETE CASCADE, NOT NULL | - | 사용자 ID |
| name | VARCHAR(200) | NOT NULL | - | 컬렉션 이름 |
| description | TEXT | - | NULL | 설명 |
| is_default | BOOLEAN | NOT NULL | FALSE | 기본 컬렉션 여부 |
| sort_order | INTEGER | NOT NULL | 0 | 정렬 순서 |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 생성 시각 |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | 수정 시각 |

**인덱스**:
- `ix_bookmark_collections_user_id` ON user_id
- `uq_bookmark_collections_user_default` UNIQUE ON user_id WHERE is_default = TRUE (partial)

### paper_bookmarks

유저-논문 북마크 관계 테이블.

| 컬럼 | 타입 | 제약 | 기본값 | 설명 |
|------|------|------|--------|------|
| id | UUID | PK | gen_random_uuid() | 북마크 ID |
| user_id | UUID | FK(users.id), ON DELETE CASCADE, NOT NULL | - | 사용자 ID |
| paper_id | UUID | FK(papers.id), ON DELETE CASCADE, NOT NULL | - | 논문 ID |
| collection_id | UUID | FK(bookmark_collections.id), ON DELETE SET NULL | NULL | 컬렉션 ID |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 북마크 시각 |

**제약조건**:
- `uq_paper_bookmarks_user_paper` UNIQUE (user_id, paper_id)

**인덱스**:
- `ix_paper_bookmarks_user_id` ON user_id
- `ix_paper_bookmarks_paper_id` ON paper_id
- `ix_paper_bookmarks_collection_id` ON collection_id

---

## DDL

```sql
-- papers 테이블에 like_count 추가
ALTER TABLE papers ADD COLUMN like_count INTEGER NOT NULL DEFAULT 0;

-- paper_likes
CREATE TABLE paper_likes (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, paper_id)
);
CREATE INDEX ix_paper_likes_paper_id ON paper_likes(paper_id);
CREATE INDEX ix_paper_likes_user_id ON paper_likes(user_id);

-- bookmark_collections
CREATE TABLE bookmark_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_bookmark_collections_user_id ON bookmark_collections(user_id);
CREATE UNIQUE INDEX uq_bookmark_collections_user_default
    ON bookmark_collections(user_id) WHERE is_default = TRUE;

-- paper_bookmarks
CREATE TABLE paper_bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES bookmark_collections(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_paper_bookmarks_user_paper UNIQUE(user_id, paper_id)
);
CREATE INDEX ix_paper_bookmarks_user_id ON paper_bookmarks(user_id);
CREATE INDEX ix_paper_bookmarks_paper_id ON paper_bookmarks(paper_id);
CREATE INDEX ix_paper_bookmarks_collection_id ON paper_bookmarks(collection_id);
```

---

## 설계 결정

| 결정 | 이유 |
|------|------|
| paper_likes 복합 PK | 별도 UUID 불필요, 공간 절약 |
| papers.like_count 캐시 | 목록 조회 시 COUNT 서브쿼리 방지 |
| 기본 컬렉션 lazy 생성 | 첫 북마크 시 자동 생성 |
| partial unique index | 유저당 기본 컬렉션 1개 보장 |
| collection_id ON DELETE SET NULL | 컬렉션 삭제 시 북마크를 기본 컬렉션으로 이동 |

---

## 주요 쿼리 패턴

```sql
-- 좋아요 토글 (추가)
INSERT INTO paper_likes (user_id, paper_id) VALUES ($1, $2);
UPDATE papers SET like_count = like_count + 1 WHERE id = $2;

-- 좋아요 토글 (제거)
DELETE FROM paper_likes WHERE user_id = $1 AND paper_id = $2;
UPDATE papers SET like_count = like_count - 1 WHERE id = $2;

-- 여러 논문의 좋아요 상태 일괄 확인
SELECT paper_id FROM paper_likes WHERE user_id = $1 AND paper_id = ANY($2);

-- 사용자의 북마크 목록 (컬렉션 필터)
SELECT pb.*, p.title, p.abstract, bc.name AS collection_name
FROM paper_bookmarks pb
JOIN papers p ON p.id = pb.paper_id
LEFT JOIN bookmark_collections bc ON bc.id = pb.collection_id
WHERE pb.user_id = $1
  AND ($2::uuid IS NULL OR pb.collection_id = $2)
ORDER BY pb.created_at DESC;
```
