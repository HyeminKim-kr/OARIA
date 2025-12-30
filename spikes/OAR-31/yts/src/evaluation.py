"""RAG 평가: GT 합성 + Retrieval 정확도 + E2E 답변 비교

GT가 없을 때의 평가 방법:
1. Synthetic QA: 청크에서 LLM으로 Q/A 쌍 생성 → 그 청크가 GT
2. Retrieval Hit Rate: 생성된 질문으로 검색 시 원본 청크가 Top-K에 있는지
3. E2E Comparison: 두 전략의 RAG 답변 품질을 LLM이 평가

실행:
    uv run python src/evaluation.py
"""

import json
import os
import random
from dataclasses import dataclass
from pathlib import Path

import weaviate
from openai import OpenAI

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

COLLECTION_A = "PaperChunk_StrategyA"
COLLECTION_B = "PaperChunk_StrategyB"

# OpenAI 클라이언트
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@dataclass
class SyntheticQA:
    """합성 Q/A 쌍"""
    chunk_id: str
    section: str
    question: str
    answer: str
    source_content: str


@dataclass
class RetrievalResult:
    """검색 결과"""
    question: str
    ground_truth_chunk_id: str
    strategy_a_hit: bool  # GT가 Top-K에 있는지
    strategy_a_rank: int  # GT의 순위 (-1이면 못 찾음)
    strategy_b_hit: bool
    strategy_b_rank: int


@dataclass
class E2EResult:
    """End-to-End 비교 결과"""
    question: str
    answer_a: str
    answer_b: str
    winner: str  # "A", "B", "TIE"
    reason: str


# ─────────────────────────────────────────────────────────────
# Step 1: Synthetic QA 생성
# ─────────────────────────────────────────────────────────────

def generate_synthetic_qa(chunks: list[dict], num_samples: int = 10) -> list[SyntheticQA]:
    """청크에서 Q/A 쌍 합성

    각 청크 내용을 기반으로 LLM이 질문과 답변을 생성
    → 해당 청크가 Ground Truth가 됨
    """
    print(f"\n[Step 1] Synthetic QA 생성 ({num_samples}개)...")

    # 다양한 섹션에서 샘플링 (abstract, results, methods 등)
    section_groups = {}
    for chunk in chunks:
        section = chunk["section"]
        if section not in section_groups:
            section_groups[section] = []
        section_groups[section].append(chunk)

    # 각 섹션에서 균등하게 샘플링
    sampled_chunks = []
    sections = list(section_groups.keys())
    random.shuffle(sections)

    for i in range(num_samples):
        section = sections[i % len(sections)]
        if section_groups[section]:
            chunk = random.choice(section_groups[section])
            sampled_chunks.append(chunk)
            section_groups[section].remove(chunk)

    # Q/A 생성
    synthetic_qas = []
    for i, chunk in enumerate(sampled_chunks):
        print(f"   [{i+1}/{len(sampled_chunks)}] {chunk['section'][:20]}...")

        prompt = f"""다음 의료 논문 텍스트를 읽고, 이 텍스트에서만 답할 수 있는 구체적인 질문과 답변을 생성하세요.

텍스트:
{chunk['content'][:1500]}

요구사항:
1. 질문은 이 텍스트의 핵심 정보를 묻는 것이어야 합니다
2. 답변은 텍스트에서 직접 찾을 수 있어야 합니다
3. 질문은 영어로, 의료 전문가가 물을 법한 질문으로 작성하세요
4. 너무 일반적인 질문은 피하세요 (예: "What is cancer?")

JSON 형식으로 응답하세요:
{{"question": "...", "answer": "..."}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            synthetic_qas.append(SyntheticQA(
                chunk_id=chunk["chunkId"],
                section=chunk["section"],
                question=result["question"],
                answer=result["answer"],
                source_content=chunk["content"][:500],
            ))
        except Exception as e:
            print(f"      Error: {e}")
            continue

    print(f"   생성 완료: {len(synthetic_qas)}개 Q/A 쌍")
    return synthetic_qas


# ─────────────────────────────────────────────────────────────
# Step 2: Retrieval 정확도 측정
# ─────────────────────────────────────────────────────────────

def measure_retrieval_accuracy(
    synthetic_qas: list[SyntheticQA],
    collection_a,
    collection_b,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """검색 정확도 측정

    합성된 질문으로 검색 → GT 청크가 Top-K에 있는지 확인
    """
    print(f"\n[Step 2] Retrieval 정확도 측정 (Top-{top_k})...")

    from embeddings import EmbeddingClient
    embedding_client = EmbeddingClient()

    results = []

    for i, qa in enumerate(synthetic_qas):
        print(f"   [{i+1}/{len(synthetic_qas)}] {qa.question[:50]}...")

        # 질문 임베딩
        query_embedding = embedding_client.embed_text(qa.question)

        # Strategy A 검색
        result_a = collection_a.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_properties=["chunkId", "content", "section"],
        )

        # Strategy B 검색
        result_b = collection_b.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_properties=["chunkId", "content", "section"],
        )

        # GT가 결과에 있는지 확인
        a_chunk_ids = [obj.properties["chunkId"] for obj in result_a.objects]
        b_chunk_ids = [obj.properties["chunkId"] for obj in result_b.objects]

        # Strategy A에서 GT 찾기
        a_hit = qa.chunk_id in a_chunk_ids
        a_rank = a_chunk_ids.index(qa.chunk_id) + 1 if a_hit else -1

        # Strategy B에서는 청크가 다를 수 있으므로 내용 기반 매칭
        # (같은 섹션의 청크 중 내용이 겹치는지 확인)
        b_hit = False
        b_rank = -1
        for idx, obj in enumerate(result_b.objects):
            # 원본 내용의 일부가 검색 결과에 포함되어 있는지 확인
            if qa.source_content[:100] in obj.properties["content"]:
                b_hit = True
                b_rank = idx + 1
                break

        results.append(RetrievalResult(
            question=qa.question,
            ground_truth_chunk_id=qa.chunk_id,
            strategy_a_hit=a_hit,
            strategy_a_rank=a_rank,
            strategy_b_hit=b_hit,
            strategy_b_rank=b_rank,
        ))

        hit_status = f"A:{'O' if a_hit else 'X'}({a_rank}) B:{'O' if b_hit else 'X'}({b_rank})"
        print(f"      {hit_status}")

    # 통계
    a_hits = sum(1 for r in results if r.strategy_a_hit)
    b_hits = sum(1 for r in results if r.strategy_b_hit)

    print(f"\n   Hit Rate@{top_k}:")
    print(f"      Strategy A: {a_hits}/{len(results)} ({a_hits/len(results)*100:.1f}%)")
    print(f"      Strategy B: {b_hits}/{len(results)} ({b_hits/len(results)*100:.1f}%)")

    return results


# ─────────────────────────────────────────────────────────────
# Step 3: End-to-End RAG 답변 비교
# ─────────────────────────────────────────────────────────────

def compare_e2e_answers(
    questions: list[str],
    collection_a,
    collection_b,
    top_k: int = 3,
) -> list[E2EResult]:
    """End-to-End RAG 답변 비교

    1. 같은 질문으로 두 전략에서 컨텍스트 검색
    2. 각각 LLM으로 답변 생성
    3. LLM이 어떤 답변이 더 나은지 평가
    """
    print(f"\n[Step 3] End-to-End RAG 답변 비교...")

    from embeddings import EmbeddingClient
    embedding_client = EmbeddingClient()

    results = []

    for i, question in enumerate(questions):
        print(f"\n   [{i+1}/{len(questions)}] {question[:50]}...")

        # 질문 임베딩
        query_embedding = embedding_client.embed_text(question)

        # 두 전략에서 컨텍스트 검색
        result_a = collection_a.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_properties=["content", "section", "title"],
        )
        result_b = collection_b.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_properties=["content", "section", "title"],
        )

        # 컨텍스트 조립
        context_a = "\n\n".join([
            f"[{j+1}] ({obj.properties['section']})\n{obj.properties['content']}"
            for j, obj in enumerate(result_a.objects)
        ])
        context_b = "\n\n".join([
            f"[{j+1}] ({obj.properties['section']})\n{obj.properties['content']}"
            for j, obj in enumerate(result_b.objects)
        ])

        # 답변 생성
        answer_a = generate_answer(question, context_a)
        answer_b = generate_answer(question, context_b)

        print(f"      A: {answer_a[:80]}...")
        print(f"      B: {answer_b[:80]}...")

        # LLM으로 답변 품질 비교
        winner, reason = compare_answers(question, answer_a, answer_b)
        print(f"      Winner: {winner} - {reason[:50]}...")

        results.append(E2EResult(
            question=question,
            answer_a=answer_a,
            answer_b=answer_b,
            winner=winner,
            reason=reason,
        ))

    # 통계
    a_wins = sum(1 for r in results if r.winner == "A")
    b_wins = sum(1 for r in results if r.winner == "B")
    ties = sum(1 for r in results if r.winner == "TIE")

    print(f"\n   E2E 비교 결과:")
    print(f"      Strategy A 승: {a_wins}")
    print(f"      Strategy B 승: {b_wins}")
    print(f"      무승부: {ties}")

    return results


def generate_answer(question: str, context: str) -> str:
    """RAG 답변 생성"""
    prompt = f"""다음 컨텍스트를 기반으로 질문에 답변하세요.

컨텍스트:
{context[:3000]}

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


def compare_answers(question: str, answer_a: str, answer_b: str) -> tuple[str, str]:
    """LLM으로 두 답변 비교"""
    prompt = f"""두 AI 시스템이 같은 질문에 대해 다른 답변을 생성했습니다.
어떤 답변이 더 나은지 평가하세요.

질문: {question}

답변 A:
{answer_a}

답변 B:
{answer_b}

평가 기준:
1. 정확성: 질문에 정확히 답하는가?
2. 완전성: 충분한 정보를 제공하는가?
3. 명확성: 이해하기 쉬운가?

JSON 형식으로 응답하세요:
{{"winner": "A" 또는 "B" 또는 "TIE", "reason": "선택 이유"}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    return result["winner"], result["reason"]


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run_evaluation(num_synthetic: int = 10, num_e2e: int = 5):
    """전체 평가 실행"""
    print("=" * 60)
    print("RAG 평가: GT 합성 + Retrieval + E2E")
    print("=" * 60)

    # Weaviate 연결
    weaviate_client = weaviate.connect_to_local()

    try:
        collection_a = weaviate_client.collections.get(COLLECTION_A)
        collection_b = weaviate_client.collections.get(COLLECTION_B)

        # 데이터 확인
        count_a = collection_a.aggregate.over_all(total_count=True).total_count
        count_b = collection_b.aggregate.over_all(total_count=True).total_count
        print(f"\n컬렉션 상태: A={count_a}개, B={count_b}개")

        if count_a == 0 or count_b == 0:
            print("데이터가 없습니다. ab_test.py --phase ingest를 먼저 실행하세요.")
            return

        # Strategy A에서 청크 가져오기 (GT 생성용)
        all_chunks_a = collection_a.query.fetch_objects(
            limit=200,
            return_properties=["chunkId", "content", "section", "title"],
        )
        chunks = [
            {
                "chunkId": obj.properties["chunkId"],
                "content": obj.properties["content"],
                "section": obj.properties["section"],
                "title": obj.properties.get("title", ""),
            }
            for obj in all_chunks_a.objects
        ]

        # Step 1: Synthetic QA 생성
        synthetic_qas = generate_synthetic_qa(chunks, num_samples=num_synthetic)

        # Step 2: Retrieval 정확도
        retrieval_results = measure_retrieval_accuracy(
            synthetic_qas, collection_a, collection_b, top_k=5
        )

        # Step 3: E2E 답변 비교
        e2e_questions = [qa.question for qa in synthetic_qas[:num_e2e]]
        e2e_results = compare_e2e_answers(
            e2e_questions, collection_a, collection_b, top_k=3
        )

        # 결과 저장
        output = {
            "synthetic_qas": [
                {"chunk_id": qa.chunk_id, "section": qa.section,
                 "question": qa.question, "answer": qa.answer}
                for qa in synthetic_qas
            ],
            "retrieval_results": [
                {"question": r.question, "gt_chunk": r.ground_truth_chunk_id,
                 "a_hit": r.strategy_a_hit, "a_rank": r.strategy_a_rank,
                 "b_hit": r.strategy_b_hit, "b_rank": r.strategy_b_rank}
                for r in retrieval_results
            ],
            "e2e_results": [
                {"question": r.question, "answer_a": r.answer_a,
                 "answer_b": r.answer_b, "winner": r.winner, "reason": r.reason}
                for r in e2e_results
            ],
            "summary": {
                "retrieval_hit_rate_a": sum(r.strategy_a_hit for r in retrieval_results) / len(retrieval_results),
                "retrieval_hit_rate_b": sum(r.strategy_b_hit for r in retrieval_results) / len(retrieval_results),
                "e2e_a_wins": sum(1 for r in e2e_results if r.winner == "A"),
                "e2e_b_wins": sum(1 for r in e2e_results if r.winner == "B"),
                "e2e_ties": sum(1 for r in e2e_results if r.winner == "TIE"),
            }
        }

        output_path = Path(__file__).parent.parent / "evaluation_results.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # 최종 요약
        print("\n" + "=" * 60)
        print("평가 결과 요약")
        print("=" * 60)
        print(f"\n## Retrieval Hit Rate@5")
        print(f"   Strategy A: {output['summary']['retrieval_hit_rate_a']*100:.1f}%")
        print(f"   Strategy B: {output['summary']['retrieval_hit_rate_b']*100:.1f}%")
        print(f"\n## E2E 답변 품질")
        print(f"   Strategy A 승: {output['summary']['e2e_a_wins']}")
        print(f"   Strategy B 승: {output['summary']['e2e_b_wins']}")
        print(f"   무승부: {output['summary']['e2e_ties']}")
        print(f"\n결과 저장: {output_path}")

        return output

    finally:
        weaviate_client.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-synthetic", type=int, default=10, help="합성 Q/A 수")
    parser.add_argument("--num-e2e", type=int, default=5, help="E2E 비교 수")
    args = parser.parse_args()

    run_evaluation(num_synthetic=args.num_synthetic, num_e2e=args.num_e2e)
