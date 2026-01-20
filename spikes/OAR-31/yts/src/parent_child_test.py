"""Parent-Child Chunking 테스트

전략 비교:
- Strategy A: 작은 청크 검색 → 작은 청크 전달
- Strategy B: 큰 청크 검색 → 큰 청크 전달
- Strategy C: 작은 청크 검색 → 부모(섹션) 전달 ⭐

실행:
    uv run python src/parent_child_test.py
"""

import json
import os
from pathlib import Path

import weaviate
from openai import OpenAI

from embeddings import EmbeddingClient

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

COLLECTION_A = "PaperChunk_StrategyA"  # 작은 청크
COLLECTION_B = "PaperChunk_StrategyB"  # 큰 청크

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
embedding_client = EmbeddingClient()


def get_parent_context(collection, chunk_id: str, paper_id: str, section: str) -> str:
    """검색된 청크의 부모(같은 섹션의 모든 청크) 가져오기"""
    from weaviate.classes.query import Filter

    # 같은 논문, 같은 섹션의 모든 청크 검색
    result = collection.query.fetch_objects(
        filters=(
            Filter.by_property("paperId").equal(paper_id) &
            Filter.by_property("section").equal(section)
        ),
        limit=20,
        return_properties=["content", "chunkIndex"],
    )

    # chunkIndex 순서로 정렬하여 원래 순서 복원
    chunks = sorted(
        [(obj.properties["chunkIndex"], obj.properties["content"]) for obj in result.objects],
        key=lambda x: x[0]
    )

    # 모든 청크 합치기 (부모 = 섹션 전체)
    parent_content = "\n\n".join([content for _, content in chunks])
    return parent_content


def generate_answer(question: str, context: str, strategy_name: str) -> str:
    """RAG 답변 생성"""
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


def compare_three_answers(question: str, answer_a: str, answer_b: str, answer_c: str) -> dict:
    """세 가지 답변 비교"""
    prompt = f"""세 AI 시스템이 같은 질문에 대해 다른 답변을 생성했습니다.
가장 좋은 답변을 선택하고 순위를 매기세요.

질문: {question}

답변 A (작은 청크 검색 → 작은 청크 전달):
{answer_a}

답변 B (큰 청크 검색 → 큰 청크 전달):
{answer_b}

답변 C (작은 청크 검색 → 부모 섹션 전달):
{answer_c}

평가 기준:
1. 정확성: 질문에 정확히 답하는가?
2. 완전성: 충분한 정보를 제공하는가?
3. 명확성: 이해하기 쉬운가?

JSON 형식으로 응답하세요:
{{"ranking": ["C", "B", "A"], "winner": "C", "reason": "선택 이유..."}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def run_test(questions: list[str] = None, top_k: int = 3):
    """Parent-Child 전략 테스트"""
    print("=" * 60)
    print("Parent-Child Chunking 전략 테스트")
    print("=" * 60)

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
        collection_a = weaviate_client.collections.get(COLLECTION_A)
        collection_b = weaviate_client.collections.get(COLLECTION_B)

        results = []

        for i, question in enumerate(questions):
            print(f"\n{'─' * 60}")
            print(f"질문 {i+1}: {question}")
            print("─" * 60)

            # 질문 임베딩
            query_embedding = embedding_client.embed_text(question)

            # ─────────────────────────────────────────────────
            # Strategy A: 작은 청크 검색 → 작은 청크 전달
            # ─────────────────────────────────────────────────
            result_a = collection_a.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_properties=["content", "section", "paperId", "chunkId"],
            )

            context_a = "\n\n".join([
                f"[{j+1}] ({obj.properties['section']})\n{obj.properties['content']}"
                for j, obj in enumerate(result_a.objects)
            ])

            answer_a = generate_answer(question, context_a, "A")
            print(f"\n[A] 작은청크→작은청크: {answer_a[:100]}...")

            # ─────────────────────────────────────────────────
            # Strategy B: 큰 청크 검색 → 큰 청크 전달
            # ─────────────────────────────────────────────────
            result_b = collection_b.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_properties=["content", "section", "paperId", "chunkId"],
            )

            context_b = "\n\n".join([
                f"[{j+1}] ({obj.properties['section']})\n{obj.properties['content']}"
                for j, obj in enumerate(result_b.objects)
            ])

            answer_b = generate_answer(question, context_b, "B")
            print(f"[B] 큰청크→큰청크: {answer_b[:100]}...")

            # ─────────────────────────────────────────────────
            # Strategy C: 작은 청크 검색 → 부모(섹션) 전달 ⭐
            # ─────────────────────────────────────────────────
            # 작은 청크로 검색 (Strategy A와 동일)
            # 하지만 검색된 청크의 부모(섹션 전체)를 가져옴

            parent_contexts = []
            seen_sections = set()

            for obj in result_a.objects:
                paper_id = obj.properties["paperId"]
                section = obj.properties["section"]
                key = f"{paper_id}|{section}"

                if key not in seen_sections:
                    seen_sections.add(key)
                    parent_content = get_parent_context(
                        collection_a,
                        obj.properties["chunkId"],
                        paper_id,
                        section
                    )
                    parent_contexts.append(f"[{section}]\n{parent_content}")

            context_c = "\n\n".join(parent_contexts)
            answer_c = generate_answer(question, context_c, "C")
            print(f"[C] 작은청크→부모섹션: {answer_c[:100]}...")

            # 세 답변 비교
            comparison = compare_three_answers(question, answer_a, answer_b, answer_c)
            print(f"\n🏆 Winner: {comparison['winner']}")
            print(f"   Ranking: {' > '.join(comparison['ranking'])}")
            print(f"   Reason: {comparison['reason'][:100]}...")

            results.append({
                "question": question,
                "answer_a": answer_a,
                "answer_b": answer_b,
                "answer_c": answer_c,
                "winner": comparison["winner"],
                "ranking": comparison["ranking"],
                "reason": comparison["reason"],
            })

        # 최종 통계
        print("\n" + "=" * 60)
        print("최종 결과")
        print("=" * 60)

        a_wins = sum(1 for r in results if r["winner"] == "A")
        b_wins = sum(1 for r in results if r["winner"] == "B")
        c_wins = sum(1 for r in results if r["winner"] == "C")

        print(f"\n승리 횟수:")
        print(f"   Strategy A (작은→작은): {a_wins}")
        print(f"   Strategy B (큰→큰):     {b_wins}")
        print(f"   Strategy C (작은→부모): {c_wins} ⭐")

        # 평균 순위 계산
        def avg_rank(strategy):
            ranks = []
            for r in results:
                if strategy in r["ranking"]:
                    ranks.append(r["ranking"].index(strategy) + 1)
            return sum(ranks) / len(ranks) if ranks else 0

        print(f"\n평균 순위 (낮을수록 좋음):")
        print(f"   Strategy A: {avg_rank('A'):.2f}")
        print(f"   Strategy B: {avg_rank('B'):.2f}")
        print(f"   Strategy C: {avg_rank('C'):.2f}")

        # 결과 저장
        output_path = Path(__file__).parent.parent / "parent_child_results.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n결과 저장: {output_path}")

        return results

    finally:
        weaviate_client.close()


if __name__ == "__main__":
    run_test()
