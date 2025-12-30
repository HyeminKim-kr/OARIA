"""Vector Store 데모

OAR-29 Chunker + OAR-31 Weaviate 연동 테스트
"""

import sys
from pathlib import Path

import weaviate
from weaviate.classes.query import Filter

# OAR-29 경로 추가
OAR_29_PATH = Path(__file__).parent.parent.parent.parent / "OAR-29" / "yts"
sys.path.insert(0, str(OAR_29_PATH))

# 현재 디렉토리를 패키지로 인식하도록
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schema import create_paper_chunk_collection, COLLECTION_NAME
from src.client import WeaviateClient
from src.embeddings import EmbeddingClient


# ─────────────────────────────────────────────────────────────
# OAR-29 데이터 로드 함수 (복사)
# ─────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "oaria",
    "user": "oaria",
    "password": "oaria123",
}

S3_CONFIG = {
    "endpoint_url": "http://localhost:9000",
    "aws_access_key_id": "minioadmin",
    "aws_secret_access_key": "minioadmin123",
    "bucket": "oaria-papers",
}


def fetch_papers_from_db(limit: int = 5) -> list[dict]:
    """PostgreSQL에서 논문 목록 조회"""
    import psycopg

    dsn = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # 논문 기본 정보 조회
            cur.execute("""
                SELECT
                    p.paper_id,
                    p.pmcid,
                    p.title,
                    p.pub_year,
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
                    "paper_id": row[0],
                    "pmcid": row[1],
                    "title": row[2],
                    "year": row[3],
                    "journal": row[4],
                    "canonical_prefix": row[5],
                    "sections": [],
                }

                # 섹션 정보 조회
                cur.execute("""
                    SELECT
                        section_name,
                        section_title,
                        content_start_offset,
                        content_end_offset
                    FROM paper_sections
                    WHERE paper_id = %s
                    ORDER BY section_order
                """, (row[0],))

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
    import boto3
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
        print(f"S3 조회 실패: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 메인 데모
# ─────────────────────────────────────────────────────────────

def run_demo():
    """Vector Store 데모 실행"""
    print("=" * 60)
    print("OAR-31: Vector Store 데모 (Weaviate + Chunker 연동)")
    print("=" * 60)

    # 1. Weaviate 연결 및 스키마 생성
    print("\n📡 Weaviate 연결 중...")
    base_client = weaviate.connect_to_local()

    try:
        # 스키마 생성
        create_paper_chunk_collection(base_client)
    finally:
        base_client.close()

    # 2. 클라이언트 초기화
    print("\n🔧 클라이언트 초기화...")
    weaviate_client = WeaviateClient()

    try:
        # 현재 객체 수 확인
        count = weaviate_client.count_objects()
        print(f"   현재 저장된 청크: {count}개")

        # 3. PostgreSQL에서 논문 조회
        print("\n📚 PostgreSQL에서 논문 조회...")
        papers = fetch_papers_from_db(limit=3)
        print(f"   조회된 논문: {len(papers)}개")

        # 4. 각 논문 처리
        from src.chunker import TextChunker

        chunker = TextChunker()
        total_inserted = 0

        for i, paper in enumerate(papers):
            print(f"\n[{i+1}/{len(papers)}] {paper['pmcid']}")
            print(f"         제목: {paper['title'][:50]}...")

            # 이미 저장된 논문인지 확인
            paper_id = f"pmc:{paper['pmcid']}"
            existing = weaviate_client.get_by_paper_id(paper_id)
            if existing:
                print(f"         ⏭️ 이미 저장됨 ({len(existing)}개 청크)")
                continue

            # S3에서 fulltext 조회
            fulltext = fetch_fulltext_from_s3(paper["canonical_prefix"])
            if not fulltext:
                print("         ❌ fulltext 조회 실패")
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

            # 메타데이터 구성
            paper_metadata = {
                "pmcid": paper["pmcid"],
                "title": paper["title"],
                "year": paper["year"],
                "journal": paper["journal"],
                "sourceUrl": f"https://europepmc.org/article/PMC/{paper['pmcid'].replace('PMC', '')}",
            }

            # Weaviate에 삽입
            print("         📤 Weaviate에 삽입 중...")
            uuids = weaviate_client.insert_chunking_result(result, paper_metadata)
            print(f"         ✅ 삽입 완료: {len(uuids)}개 청크")
            total_inserted += len(uuids)

        # 5. 최종 통계
        final_count = weaviate_client.count_objects()
        print(f"\n📊 최종 통계:")
        print(f"   - 새로 삽입: {total_inserted}개 청크")
        print(f"   - 전체 저장: {final_count}개 청크")

        # 6. 검색 테스트
        if final_count > 0:
            print("\n" + "=" * 60)
            print("🔍 검색 테스트")
            print("=" * 60)

            test_query = "cancer immunotherapy treatment"

            # 벡터 검색
            print(f"\n1️⃣ 벡터 검색: '{test_query}'")
            results = weaviate_client.search_by_vector(test_query, limit=3)
            for j, r in enumerate(results):
                print(f"   [{j+1}] {r['properties']['title'][:40]}... | {r['properties']['section']}")
                print(f"       거리: {r['distance']:.4f}")
                print(f"       내용: {r['properties']['content'][:80]}...")

            # 하이브리드 검색
            print(f"\n2️⃣ 하이브리드 검색: '{test_query}'")
            results = weaviate_client.search_hybrid(test_query, limit=3, alpha=0.5)
            for j, r in enumerate(results):
                print(f"   [{j+1}] {r['properties']['title'][:40]}... | {r['properties']['section']}")
                print(f"       점수: {r['score']:.4f}")

            # 필터 검색
            print(f"\n3️⃣ 필터 + 벡터 검색: section='abstract'")
            results = weaviate_client.search_by_vector(
                test_query,
                limit=3,
                filters=Filter.by_property("section").equal("abstract"),
            )
            for j, r in enumerate(results):
                print(f"   [{j+1}] {r['properties']['title'][:40]}...")
                print(f"       섹션: {r['properties']['section']}")

    finally:
        weaviate_client.close()

    print("\n🎉 데모 완료!")


if __name__ == "__main__":
    run_demo()
