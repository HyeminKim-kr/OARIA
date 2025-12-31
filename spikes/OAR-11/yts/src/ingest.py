"""논문 적재 파이프라인

PostgreSQL → MinIO → Chunker → Embeddings → Weaviate
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
import uuid

import boto3
import psycopg
import weaviate
import weaviate.classes as wvc
from weaviate.classes.query import Filter

# OAR-29 Chunker 임포트
OAR_29_PATH = Path(__file__).parent.parent.parent.parent / "OAR-29" / "yts" / "src"
sys.path.insert(0, str(OAR_29_PATH))
from chunker import TextChunker

# OAR-31 Weaviate 임포트
OAR_31_PATH = Path(__file__).parent.parent.parent.parent / "OAR-31" / "yts" / "src"
sys.path.insert(0, str(OAR_31_PATH))
from schema import create_paper_chunk_collection, COLLECTION_NAME
from embeddings import EmbeddingClient


# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": "localhost",
    "port": 15432,  # spikes/yts Docker 포트
    "dbname": "oaria",
    "user": "oaria",
    "password": "oaria_dev_2024",
}

S3_CONFIG = {
    "endpoint_url": "http://localhost:19000",  # spikes/yts Docker 포트
    "aws_access_key_id": "minioadmin",
    "aws_secret_access_key": "minioadmin_2024",
    "bucket": "oaria-papers",
}


# ─────────────────────────────────────────────────────────────
# 데이터 조회
# ─────────────────────────────────────────────────────────────

def fetch_papers_from_db(limit: int = 10) -> list[dict]:
    """PostgreSQL에서 논문 목록 조회"""
    dsn = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.id,
                    p.paper_id,
                    p.pmcid,
                    p.title,
                    p.year,
                    p.journal,
                    p.canonical_prefix
                FROM papers p
                WHERE p.canonical_prefix IS NOT NULL
                ORDER BY p.created_at DESC
                LIMIT %s
            """, (limit,))

            papers = []
            for row in cur.fetchall():
                paper = {
                    "id": row[0],  # UUID
                    "paper_id": row[1],  # pmc:PMCxxx 형식
                    "pmcid": row[2],
                    "title": row[3],
                    "year": row[4],
                    "journal": row[5],
                    "canonical_prefix": row[6],
                    "sections": [],
                }

                # 섹션 정보 조회 (paper_id는 UUID 참조)
                cur.execute("""
                    SELECT
                        section_name,
                        section_title,
                        offset_start,
                        offset_end
                    FROM paper_sections
                    WHERE paper_id = %s
                    ORDER BY section_order
                """, (row[0],))  # UUID 사용

                for sec_row in cur.fetchall():
                    paper["sections"].append({
                        "name": sec_row[0],
                        "title": sec_row[1],
                        "offset_start": sec_row[2],
                        "offset_end": sec_row[3],
                    })

                papers.append(paper)

    return papers


def fetch_fulltext_from_s3(canonical_prefix: str) -> str | None:
    """MinIO에서 fulltext 조회"""
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=S3_CONFIG["endpoint_url"],
        aws_access_key_id=S3_CONFIG["aws_access_key_id"],
        aws_secret_access_key=S3_CONFIG["aws_secret_access_key"],
    )

    try:
        response = client.get_object(
            Bucket=S3_CONFIG["bucket"],
            Key=f"{canonical_prefix}/fulltext.txt",
        )
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        print(f"   ❌ S3 조회 실패: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 적재 파이프라인
# ─────────────────────────────────────────────────────────────

def ingest_papers(limit: int = 10, batch_size: int = 10):
    """논문 적재 실행"""
    print("=" * 60)
    print("OAR-11: 논문 적재 파이프라인")
    print("=" * 60)

    # 1. Weaviate 연결 및 스키마 생성
    print("\n📡 Weaviate 연결...")
    base_client = weaviate.connect_to_local()
    try:
        create_paper_chunk_collection(base_client)
    finally:
        base_client.close()

    # 2. 클라이언트 초기화
    print("\n🔧 클라이언트 초기화...")
    weaviate_client = weaviate.connect_to_local()
    collection = weaviate_client.collections.get(COLLECTION_NAME)
    embedding_client = EmbeddingClient()
    chunker = TextChunker()

    print(f"   임베딩: {embedding_client.get_version_string()}")

    try:
        # 현재 저장된 객체 수
        count_before = collection.aggregate.over_all(total_count=True).total_count
        print(f"   현재 저장된 청크: {count_before}개")

        # 3. PostgreSQL에서 논문 조회
        print(f"\n📚 PostgreSQL에서 논문 조회 (limit={limit})...")
        papers = fetch_papers_from_db(limit=limit)
        print(f"   조회된 논문: {len(papers)}개")

        # 4. 각 논문 처리
        total_chunks = 0
        for i, paper in enumerate(papers):
            print(f"\n[{i+1}/{len(papers)}] {paper['pmcid']}")
            print(f"         제목: {paper['title'][:50]}...")

            paper_id = f"pmc:{paper['pmcid']}"

            # 이미 저장된 논문인지 확인
            existing = collection.query.fetch_objects(
                filters=Filter.by_property("paperId").equal(paper_id),
                limit=1,
            )
            if existing.objects:
                print(f"         ⏭️ 이미 저장됨")
                continue

            # S3에서 fulltext 조회
            fulltext = fetch_fulltext_from_s3(paper["canonical_prefix"])
            if not fulltext:
                continue

            # 청킹
            result = chunker.chunk_paper(
                paper_id=paper_id,
                title=paper["title"],
                fulltext=fulltext,
                sections=paper["sections"],
                year=paper["year"],
            )
            print(f"         📄 청크: {len(result.chunks)}개")

            # 배치 임베딩 + 저장
            chunks = result.chunks
            for j in range(0, len(chunks), batch_size):
                batch_chunks = chunks[j:j + batch_size]
                batch_texts = [c.embedding_input for c in batch_chunks]
                batch_embeddings = embedding_client.embed_texts(batch_texts)

                # Weaviate 삽입
                for chunk, embedding in zip(batch_chunks, batch_embeddings):
                    object_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
                    collection.data.insert(
                        uuid=object_uuid,
                        properties={
                            "paperId": chunk.paper_id,
                            "chunkId": chunk.chunk_id,
                            "embeddingVersion": embedding_client.get_version_string(),
                            "pmcid": paper["pmcid"],
                            "title": paper["title"],
                            "journal": paper.get("journal"),
                            "year": paper.get("year"),
                            "section": chunk.section,
                            "chunkIndex": chunk.chunk_index,
                            "content": chunk.text,
                            "offsetStart": chunk.offset_start,
                            "offsetEnd": chunk.offset_end,
                            "textVersion": chunk.text_version,
                            "sourceUrl": f"https://europepmc.org/article/PMC/{paper['pmcid'].replace('PMC', '')}",
                            "createdAt": datetime.now(timezone.utc),
                        },
                        vector=embedding,
                    )

                print(f"         📤 저장: {min(j + batch_size, len(chunks))}/{len(chunks)}")

            total_chunks += len(chunks)

        # 5. 최종 통계
        count_after = collection.aggregate.over_all(total_count=True).total_count
        print(f"\n📊 적재 완료:")
        print(f"   - 새로 저장: {count_after - count_before}개 청크")
        print(f"   - 전체 저장: {count_after}개 청크")

    finally:
        weaviate_client.close()

    print("\n✅ 적재 완료!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="논문 수")
    args = parser.parse_args()

    ingest_papers(limit=args.limit)
