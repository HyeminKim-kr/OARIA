"""A/B 테스트: 청킹 전략 비교

Strategy A (FIXED): 모든 섹션을 700토큰 단위로 분할
Strategy B (ADAPTIVE): 800토큰 이하 섹션은 그대로 유지

실행:
    uv run python src/ab_test.py --phase ingest   # 데이터 적재
    uv run python src/ab_test.py --phase search   # 검색 비교
    uv run python src/ab_test.py --phase report   # 결과 리포트
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
import argparse

import boto3
import psycopg
import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import DataType, Property, VectorDistances, Configure
from weaviate.classes.query import Filter

from adaptive_chunker import AdaptiveChunker, ChunkingStrategy, compare_strategies
from embeddings import EmbeddingClient


# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": "localhost",
    "port": 15432,
    "dbname": "oaria",
    "user": "oaria",
    "password": "oaria_dev_2024",
}

S3_CONFIG = {
    "endpoint_url": "http://localhost:19000",
    "aws_access_key_id": "minioadmin",
    "aws_secret_access_key": "minioadmin_2024",
    "bucket": "oaria-papers",
}

# A/B 테스트용 컬렉션 이름
COLLECTION_A = "PaperChunk_StrategyA"  # FIXED
COLLECTION_B = "PaperChunk_StrategyB"  # ADAPTIVE

# 테스트 질문 목록
TEST_QUESTIONS = [
    "What is the mechanism of EGFR inhibitors in lung cancer treatment?",
    "How does PD-L1 expression affect immunotherapy response?",
    "What are the side effects of chemotherapy in breast cancer patients?",
    "What is the role of BRCA mutations in ovarian cancer?",
    "How effective is CAR-T therapy for leukemia?",
]


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
                    "id": row[0],
                    "paper_id": row[1],
                    "pmcid": row[2],
                    "title": row[3],
                    "year": row[4],
                    "journal": row[5],
                    "canonical_prefix": row[6],
                    "sections": [],
                }

                cur.execute("""
                    SELECT
                        section_name,
                        section_title,
                        offset_start,
                        offset_end
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
        print(f"   S3 조회 실패: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Weaviate 스키마
# ─────────────────────────────────────────────────────────────

def create_ab_collections(client: weaviate.WeaviateClient):
    """A/B 테스트용 컬렉션 생성"""
    for collection_name in [COLLECTION_A, COLLECTION_B]:
        if client.collections.exists(collection_name):
            print(f"   {collection_name} 이미 존재 (삭제 후 재생성)")
            client.collections.delete(collection_name)

        client.collections.create(
            name=collection_name,
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
            ),
            properties=[
                Property(name="paperId", data_type=DataType.TEXT),
                Property(name="chunkId", data_type=DataType.TEXT),
                Property(name="pmcid", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="section", data_type=DataType.TEXT),
                Property(name="chunkIndex", data_type=DataType.INT),
                Property(name="content", data_type=DataType.TEXT),
                Property(name="tokenCount", data_type=DataType.INT),
                Property(name="strategy", data_type=DataType.TEXT),
                Property(name="offsetStart", data_type=DataType.INT),
                Property(name="offsetEnd", data_type=DataType.INT),
            ],
        )
        print(f"   {collection_name} 생성 완료")


# ─────────────────────────────────────────────────────────────
# Phase 1: 데이터 적재
# ─────────────────────────────────────────────────────────────

def run_ingest(limit: int = 5, batch_size: int = 10):
    """두 전략으로 데이터 적재"""
    print("=" * 60)
    print("A/B 테스트: 데이터 적재 (Phase 1)")
    print("=" * 60)

    # Weaviate 연결 및 스키마 생성
    print("\n[1] Weaviate 연결 및 컬렉션 생성...")
    client = weaviate.connect_to_local()

    try:
        create_ab_collections(client)

        collection_a = client.collections.get(COLLECTION_A)
        collection_b = client.collections.get(COLLECTION_B)

        # 임베딩 클라이언트
        embedding_client = EmbeddingClient()
        print(f"   임베딩: {embedding_client.get_version_string()}")

        # 청커 초기화
        # Strategy A: 500토큰 초과 시 분할 (더 공격적)
        # Strategy B: 1000토큰 초과 시 분할 (섹션 보존 우선)
        chunker_a = AdaptiveChunker(
            strategy=ChunkingStrategy.FIXED,
            chunk_size_tokens=500,
        )
        chunker_b = AdaptiveChunker(
            strategy=ChunkingStrategy.ADAPTIVE,
            chunk_size_tokens=700,
            adaptive_threshold_tokens=1000,  # 1000토큰 이하 섹션은 보존
        )

        # 논문 조회
        print(f"\n[2] PostgreSQL에서 논문 조회 (limit={limit})...")
        papers = fetch_papers_from_db(limit=limit)
        print(f"   조회된 논문: {len(papers)}개")

        # 청킹 비교 통계
        stats = {
            "a": {"total_chunks": 0, "preserved": 0, "split": 0},
            "b": {"total_chunks": 0, "preserved": 0, "split": 0},
        }

        # 각 논문 처리
        print(f"\n[3] 청킹 및 적재...")
        for i, paper in enumerate(papers):
            print(f"\n   [{i+1}/{len(papers)}] {paper['pmcid']}: {paper['title'][:40]}...")

            paper_id = f"pmc:{paper['pmcid']}"

            # S3에서 fulltext 조회
            fulltext = fetch_fulltext_from_s3(paper["canonical_prefix"])
            if not fulltext:
                continue

            # Strategy A 청킹
            result_a = chunker_a.chunk_paper(
                paper_id=paper_id,
                title=paper["title"],
                fulltext=fulltext,
                sections=paper["sections"],
                year=paper["year"],
            )

            # Strategy B 청킹
            result_b = chunker_b.chunk_paper(
                paper_id=paper_id,
                title=paper["title"],
                fulltext=fulltext,
                sections=paper["sections"],
                year=paper["year"],
            )

            print(f"      Strategy A (FIXED):    {len(result_a.chunks)}개 청크")
            print(f"      Strategy B (ADAPTIVE): {len(result_b.chunks)}개 청크 "
                  f"(보존: {result_b.preserved_sections}, 분할: {result_b.split_sections})")

            # 통계 업데이트
            stats["a"]["total_chunks"] += len(result_a.chunks)
            stats["a"]["preserved"] += result_a.preserved_sections
            stats["a"]["split"] += result_a.split_sections
            stats["b"]["total_chunks"] += len(result_b.chunks)
            stats["b"]["preserved"] += result_b.preserved_sections
            stats["b"]["split"] += result_b.split_sections

            # 임베딩 및 저장 - Strategy A
            def save_chunks(collection, chunks, prefix, paper_meta):
                for j in range(0, len(chunks), batch_size):
                    batch = chunks[j:j + batch_size]
                    embeddings = embedding_client.embed_texts([c.embedding_input for c in batch])

                    with collection.batch.fixed_size(batch_size=batch_size) as batch_inserter:
                        for chunk, emb in zip(batch, embeddings):
                            batch_inserter.add_object(
                                uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{prefix}:{chunk.chunk_id}")),
                                properties={
                                    "paperId": chunk.paper_id,
                                    "chunkId": chunk.chunk_id,
                                    "pmcid": paper_meta["pmcid"],
                                    "title": paper_meta["title"],
                                    "section": chunk.section,
                                    "chunkIndex": chunk.chunk_index,
                                    "content": chunk.text,
                                    "tokenCount": chunk.token_count,
                                    "strategy": chunk.strategy,
                                    "offsetStart": chunk.offset_start,
                                    "offsetEnd": chunk.offset_end,
                                },
                                vector=emb,
                            )

            save_chunks(collection_a, result_a.chunks, "a", paper)
            save_chunks(collection_b, result_b.chunks, "b", paper)

        # 최종 통계
        print("\n" + "=" * 60)
        print("적재 완료 - 통계")
        print("=" * 60)
        print(f"\nStrategy A (FIXED - 700토큰 분할):")
        print(f"   총 청크: {stats['a']['total_chunks']}개")

        print(f"\nStrategy B (ADAPTIVE - 800토큰 기준):")
        print(f"   총 청크: {stats['b']['total_chunks']}개")
        print(f"   보존된 섹션: {stats['b']['preserved']}개")
        print(f"   분할된 섹션: {stats['b']['split']}개")

        reduction = (1 - stats['b']['total_chunks'] / stats['a']['total_chunks']) * 100 if stats['a']['total_chunks'] > 0 else 0
        print(f"\n   청크 수 감소율: {reduction:.1f}%")

    finally:
        client.close()


# ─────────────────────────────────────────────────────────────
# Phase 2: 검색 비교
# ─────────────────────────────────────────────────────────────

def run_search(questions: list[str] = None, top_k: int = 3):
    """두 전략의 검색 결과 비교"""
    print("=" * 60)
    print("A/B 테스트: 검색 비교 (Phase 2)")
    print("=" * 60)

    if questions is None:
        questions = TEST_QUESTIONS

    client = weaviate.connect_to_local()
    embedding_client = EmbeddingClient()

    try:
        collection_a = client.collections.get(COLLECTION_A)
        collection_b = client.collections.get(COLLECTION_B)

        # 컬렉션 상태 확인
        count_a = collection_a.aggregate.over_all(total_count=True).total_count
        count_b = collection_b.aggregate.over_all(total_count=True).total_count
        print(f"\n컬렉션 상태:")
        print(f"   Strategy A: {count_a}개 청크")
        print(f"   Strategy B: {count_b}개 청크")

        if count_a == 0 or count_b == 0:
            print("\n데이터가 없습니다. 먼저 --phase ingest를 실행하세요.")
            return

        results = []

        for q_idx, question in enumerate(questions):
            print(f"\n{'─' * 60}")
            print(f"질문 {q_idx + 1}: {question}")
            print("─" * 60)

            # 질문 임베딩
            query_embedding = embedding_client.embed_text(question)

            # Strategy A 검색
            result_a = collection_a.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_metadata=["distance"],
            )

            # Strategy B 검색
            result_b = collection_b.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_metadata=["distance"],
            )

            print("\n[Strategy A - FIXED]")
            for i, obj in enumerate(result_a.objects):
                print(f"  {i+1}. [{obj.properties['section']}] "
                      f"{obj.properties['content'][:80]}...")
                print(f"      토큰: {obj.properties['tokenCount']}, "
                      f"거리: {obj.metadata.distance:.4f}")

            print("\n[Strategy B - ADAPTIVE]")
            for i, obj in enumerate(result_b.objects):
                print(f"  {i+1}. [{obj.properties['section']}] "
                      f"{obj.properties['content'][:80]}...")
                print(f"      토큰: {obj.properties['tokenCount']}, "
                      f"거리: {obj.metadata.distance:.4f}")

            # 결과 저장
            results.append({
                "question": question,
                "strategy_a": [
                    {
                        "section": obj.properties["section"],
                        "content_preview": obj.properties["content"][:100],
                        "token_count": obj.properties["tokenCount"],
                        "distance": obj.metadata.distance,
                    }
                    for obj in result_a.objects
                ],
                "strategy_b": [
                    {
                        "section": obj.properties["section"],
                        "content_preview": obj.properties["content"][:100],
                        "token_count": obj.properties["tokenCount"],
                        "distance": obj.metadata.distance,
                    }
                    for obj in result_b.objects
                ],
            })

        # 결과 저장
        output_path = Path(__file__).parent.parent / "ab_test_results.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n결과 저장: {output_path}")

    finally:
        client.close()


# ─────────────────────────────────────────────────────────────
# Phase 3: 리포트
# ─────────────────────────────────────────────────────────────

def run_report():
    """A/B 테스트 결과 리포트"""
    print("=" * 60)
    print("A/B 테스트: 결과 리포트 (Phase 3)")
    print("=" * 60)

    client = weaviate.connect_to_local()

    try:
        collection_a = client.collections.get(COLLECTION_A)
        collection_b = client.collections.get(COLLECTION_B)

        # 기본 통계
        count_a = collection_a.aggregate.over_all(total_count=True).total_count
        count_b = collection_b.aggregate.over_all(total_count=True).total_count

        print("\n## 청킹 통계")
        print(f"- Strategy A (FIXED): {count_a}개 청크")
        print(f"- Strategy B (ADAPTIVE): {count_b}개 청크")

        if count_a > 0:
            reduction = (1 - count_b / count_a) * 100
            print(f"- 청크 수 감소: {reduction:.1f}%")

        # 섹션별 분포
        print("\n## 섹션별 청크 분포")

        for strategy, collection in [("A (FIXED)", collection_a), ("B (ADAPTIVE)", collection_b)]:
            print(f"\n### Strategy {strategy}")

            # 모든 청크 조회
            all_chunks = collection.query.fetch_objects(limit=1000)

            section_stats = {}
            for obj in all_chunks.objects:
                section = obj.properties["section"]
                tokens = obj.properties["tokenCount"]

                if section not in section_stats:
                    section_stats[section] = {"count": 0, "total_tokens": 0, "tokens": []}
                section_stats[section]["count"] += 1
                section_stats[section]["total_tokens"] += tokens
                section_stats[section]["tokens"].append(tokens)

            for section, stats in sorted(section_stats.items()):
                avg_tokens = stats["total_tokens"] / stats["count"] if stats["count"] > 0 else 0
                min_tokens = min(stats["tokens"]) if stats["tokens"] else 0
                max_tokens = max(stats["tokens"]) if stats["tokens"] else 0
                print(f"  - {section}: {stats['count']}개, "
                      f"평균 {avg_tokens:.0f}토큰 (범위: {min_tokens}-{max_tokens})")

        # 검색 결과 파일 확인
        results_path = Path(__file__).parent.parent / "ab_test_results.json"
        if results_path.exists():
            print("\n## 검색 품질 비교")
            with open(results_path) as f:
                results = json.load(f)

            # 평균 거리 비교
            avg_dist_a = []
            avg_dist_b = []

            for r in results:
                if r["strategy_a"]:
                    avg_dist_a.append(sum(x["distance"] for x in r["strategy_a"]) / len(r["strategy_a"]))
                if r["strategy_b"]:
                    avg_dist_b.append(sum(x["distance"] for x in r["strategy_b"]) / len(r["strategy_b"]))

            if avg_dist_a and avg_dist_b:
                print(f"- Strategy A 평균 거리: {sum(avg_dist_a)/len(avg_dist_a):.4f}")
                print(f"- Strategy B 평균 거리: {sum(avg_dist_b)/len(avg_dist_b):.4f}")

                if sum(avg_dist_b)/len(avg_dist_b) < sum(avg_dist_a)/len(avg_dist_a):
                    print("\n  Strategy B (ADAPTIVE)가 더 가까운 결과를 반환합니다.")
                else:
                    print("\n  Strategy A (FIXED)가 더 가까운 결과를 반환합니다.")

        print("\n## 결론")
        print("- ADAPTIVE 전략은 짧은 섹션(Abstract 등)을 그대로 유지하여 의미적 완결성 보존")
        print("- 청크 수 감소로 스토리지 및 검색 비용 절감")
        print("- 실제 검색 품질은 질문 유형과 데이터에 따라 다를 수 있음")

    finally:
        client.close()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A/B 테스트: 청킹 전략 비교")
    parser.add_argument(
        "--phase",
        choices=["ingest", "search", "report", "all"],
        default="all",
        help="실행할 단계",
    )
    parser.add_argument("--limit", type=int, default=5, help="적재할 논문 수")
    parser.add_argument("--top-k", type=int, default=3, help="검색 결과 수")

    args = parser.parse_args()

    if args.phase == "ingest":
        run_ingest(limit=args.limit)
    elif args.phase == "search":
        run_search(top_k=args.top_k)
    elif args.phase == "report":
        run_report()
    else:
        run_ingest(limit=args.limit)
        run_search(top_k=args.top_k)
        run_report()
