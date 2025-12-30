"""Parent Retrieval 방식 비교

두 가지 Parent Retrieval 방식 비교:
1. Weaviate 기반: 같은 섹션의 청크들을 조회해서 합치기
2. S3 + Offset 기반: PostgreSQL에서 offset 조회 → S3에서 원본 섹션 추출

실행:
    uv run python src/parent_retrieval_comparison.py
"""

import json
import os
from pathlib import Path

import boto3
import psycopg
import weaviate
from weaviate.classes.query import Filter
from openai import OpenAI

from embeddings import EmbeddingClient

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

COLLECTION_A = "PaperChunk_StrategyA"  # 작은 청크

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

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
embedding_client = EmbeddingClient()


# ─────────────────────────────────────────────────────────────
# Parent Retrieval 방식 1: Weaviate 기반
# ─────────────────────────────────────────────────────────────

def get_parent_via_weaviate(collection, paper_id: str, section: str) -> str:
    """Weaviate에서 같은 섹션의 모든 청크를 조회하여 합치기

    장점: 한 시스템에서 처리, 빠름
    단점: 청크 분할 시 경계에서 손실 가능
    """
    result = collection.query.fetch_objects(
        filters=(
            Filter.by_property("paperId").equal(paper_id) &
            Filter.by_property("section").equal(section)
        ),
        limit=50,
        return_properties=["content", "chunkIndex"],
    )

    if not result.objects:
        return ""

    # chunkIndex 순서로 정렬
    chunks = sorted(
        [(obj.properties["chunkIndex"], obj.properties["content"])
         for obj in result.objects],
        key=lambda x: x[0]
    )

    # 청크들 합치기
    return "\n\n".join([content for _, content in chunks])


# ─────────────────────────────────────────────────────────────
# Parent Retrieval 방식 2: S3 + Offset 기반
# ─────────────────────────────────────────────────────────────

def get_section_offset_from_db(pmcid: str, section_name: str) -> tuple[int, int] | None:
    """PostgreSQL에서 섹션의 offset 조회"""
    dsn = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ps.offset_start, ps.offset_end
                FROM paper_sections ps
                JOIN papers p ON ps.paper_id = p.id
                WHERE p.pmcid = %s AND ps.section_name = %s
            """, (pmcid, section_name))

            row = cur.fetchone()
            if row:
                return (row[0], row[1])
            return None


def get_canonical_prefix_from_db(pmcid: str) -> str | None:
    """PostgreSQL에서 canonical_prefix 조회"""
    dsn = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT canonical_prefix FROM papers WHERE pmcid = %s
            """, (pmcid,))

            row = cur.fetchone()
            if row:
                return row[0]
            return None


def get_fulltext_from_s3(canonical_prefix: str) -> str | None:
    """S3에서 fulltext 조회"""
    from botocore.exceptions import ClientError

    s3_client = boto3.client(
        "s3",
        endpoint_url=S3_CONFIG["endpoint_url"],
        aws_access_key_id=S3_CONFIG["aws_access_key_id"],
        aws_secret_access_key=S3_CONFIG["aws_secret_access_key"],
    )

    try:
        response = s3_client.get_object(
            Bucket=S3_CONFIG["bucket"],
            Key=f"{canonical_prefix}/fulltext.txt",
        )
        return response["Body"].read().decode("utf-8")
    except ClientError:
        return None


def get_parent_via_s3_offset(pmcid: str, section_name: str) -> str:
    """S3 + Offset 기반으로 원본 섹션 추출

    장점: 원본 그대로, 청크 경계 손실 없음
    단점: PostgreSQL + S3 두 번 호출
    """
    # 1. canonical_prefix 조회
    canonical_prefix = get_canonical_prefix_from_db(pmcid)
    if not canonical_prefix:
        return ""

    # 2. 섹션 offset 조회
    offsets = get_section_offset_from_db(pmcid, section_name)
    if not offsets:
        return ""

    offset_start, offset_end = offsets

    # 3. S3에서 fulltext 가져오기
    fulltext = get_fulltext_from_s3(canonical_prefix)
    if not fulltext:
        return ""

    # 4. offset으로 섹션 추출
    return fulltext[offset_start:offset_end]


# ─────────────────────────────────────────────────────────────
# RAG 답변 생성
# ─────────────────────────────────────────────────────────────

def generate_answer(question: str, context: str) -> str:
    """RAG 답변 생성"""
    if not context.strip():
        return "컨텍스트 없음"

    prompt = f"""다음 컨텍스트를 기반으로 질문에 답변하세요.

컨텍스트:
{context[:4000]}

질문: {question}

요구사항:
- 컨텍스트에 있는 정보만 사용하세요
- 간결하고 정확하게 답변하세요
- 관련 정보가 없으면 "정보 없음"이라고 하세요"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )

    return response.choices[0].message.content


def compare_answers(question: str, answer_weaviate: str, answer_s3: str) -> dict:
    """두 답변 비교"""
    prompt = f"""두 AI 시스템이 같은 질문에 대해 다른 답변을 생성했습니다.
어떤 답변이 더 나은지 평가하세요.

질문: {question}

답변 W (Weaviate 기반 - 청크 합치기):
{answer_weaviate}

답변 S (S3 기반 - 원본 섹션):
{answer_s3}

평가 기준:
1. 정확성: 질문에 정확히 답하는가?
2. 완전성: 충분한 정보를 제공하는가?
3. 명확성: 이해하기 쉬운가?

JSON 형식으로 응답:
{{"winner": "W" 또는 "S" 또는 "TIE", "reason": "선택 이유..."}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


# ─────────────────────────────────────────────────────────────
# 메인 테스트
# ─────────────────────────────────────────────────────────────

def run_comparison(questions: list[str] = None, top_k: int = 3):
    """두 Parent Retrieval 방식 비교"""
    print("=" * 60)
    print("Parent Retrieval 방식 비교")
    print("=" * 60)
    print("\n방식 W: Weaviate 기반 (청크 합치기)")
    print("방식 S: S3 + Offset 기반 (원본 섹션)")

    if questions is None:
        questions = [
            "What is the relationship between BRCA mutations and prostate cancer prognosis?",
            "How does PD-L1 expression affect immunotherapy response rates?",
            "What are the mechanisms of platinum-based drug resistance?",
            "What is the role of CD248 in tumor microenvironment?",
            "How effective is the combination of carboplatin and paclitaxel?",
        ]

    weaviate_client = weaviate.connect_to_local()

    try:
        collection = weaviate_client.collections.get(COLLECTION_A)

        results = []

        for i, question in enumerate(questions):
            print(f"\n{'─' * 60}")
            print(f"질문 {i+1}: {question}")
            print("─" * 60)

            # 질문 임베딩
            query_embedding = embedding_client.embed_text(question)

            # 작은 청크로 검색
            search_result = collection.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_properties=["paperId", "section", "pmcid", "content"],
            )

            if not search_result.objects:
                print("   검색 결과 없음")
                continue

            # 검색된 청크들의 부모 섹션 수집 (중복 제거)
            seen_sections = set()
            weaviate_contexts = []
            s3_contexts = []

            for obj in search_result.objects:
                paper_id = obj.properties["paperId"]
                section = obj.properties["section"]
                pmcid = obj.properties["pmcid"]
                key = f"{paper_id}|{section}"

                if key in seen_sections:
                    continue
                seen_sections.add(key)

                print(f"\n   섹션: {section} ({pmcid})")

                # 방식 W: Weaviate 기반
                parent_w = get_parent_via_weaviate(collection, paper_id, section)
                weaviate_contexts.append(f"[{section}]\n{parent_w}")
                print(f"   W 길이: {len(parent_w)} chars")

                # 방식 S: S3 + Offset 기반
                parent_s = get_parent_via_s3_offset(pmcid, section)
                s3_contexts.append(f"[{section}]\n{parent_s}")
                print(f"   S 길이: {len(parent_s)} chars")

                # 내용 차이 확인
                if parent_w and parent_s:
                    diff = abs(len(parent_w) - len(parent_s))
                    match_ratio = min(len(parent_w), len(parent_s)) / max(len(parent_w), len(parent_s)) * 100
                    print(f"   차이: {diff} chars ({match_ratio:.1f}% 일치)")

            # 컨텍스트 합치기
            context_w = "\n\n".join(weaviate_contexts)
            context_s = "\n\n".join(s3_contexts)

            # 답변 생성
            print("\n   답변 생성 중...")
            answer_w = generate_answer(question, context_w)
            answer_s = generate_answer(question, context_s)

            print(f"\n   [W] {answer_w[:100]}...")
            print(f"   [S] {answer_s[:100]}...")

            # 답변 비교
            comparison = compare_answers(question, answer_w, answer_s)
            print(f"\n   🏆 Winner: {comparison['winner']}")
            print(f"   Reason: {comparison['reason'][:80]}...")

            results.append({
                "question": question,
                "context_w_length": len(context_w),
                "context_s_length": len(context_s),
                "answer_w": answer_w,
                "answer_s": answer_s,
                "winner": comparison["winner"],
                "reason": comparison["reason"],
            })

        # 최종 결과
        print("\n" + "=" * 60)
        print("최종 결과")
        print("=" * 60)

        w_wins = sum(1 for r in results if r["winner"] == "W")
        s_wins = sum(1 for r in results if r["winner"] == "S")
        ties = sum(1 for r in results if r["winner"] == "TIE")

        print(f"\n승리 횟수:")
        print(f"   방식 W (Weaviate 청크 합치기): {w_wins}")
        print(f"   방식 S (S3 원본 섹션):        {s_wins}")
        print(f"   무승부:                       {ties}")

        # 평균 컨텍스트 길이
        avg_w = sum(r["context_w_length"] for r in results) / len(results)
        avg_s = sum(r["context_s_length"] for r in results) / len(results)
        print(f"\n평균 컨텍스트 길이:")
        print(f"   방식 W: {avg_w:.0f} chars")
        print(f"   방식 S: {avg_s:.0f} chars")

        # 결과 저장
        output_path = Path(__file__).parent.parent / "parent_retrieval_comparison.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n결과 저장: {output_path}")

        return results

    finally:
        weaviate_client.close()


if __name__ == "__main__":
    run_comparison()
