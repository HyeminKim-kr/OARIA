"""RAG 시스템 평가 스크립트

RAGAS 스타일의 자동 평가 (LLM 기반):
- Retrieval Quality: 검색된 문서가 올바른 논문인지
- Faithfulness: 답변이 컨텍스트에 근거하는지
- Answer Relevancy: 답변이 질문에 관련있는지
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass

import weaviate
from weaviate.classes.query import MetadataQuery
from openai import OpenAI

# OAR-31 Weaviate 임포트
OAR_31_PATH = Path(__file__).parent.parent.parent.parent / "OAR-31" / "yts" / "src"
sys.path.insert(0, str(OAR_31_PATH))
from schema import COLLECTION_NAME
from embeddings import EmbeddingClient


# ─────────────────────────────────────────────────────────────
# 평가 데이터셋 (Ground Truth 포함)
# ─────────────────────────────────────────────────────────────

EVAL_DATASET = [
    {
        "question": "What is the role of neutrophils in lung cancer immunotherapy?",
        "expected_pmcid": "PMC12625643",
        "key_concepts": ["neutrophils", "lung cancer", "immunotherapy", "PD-1", "PD-L1"],
    },
    {
        "question": "How does KRAS mutation affect immune response in cancer?",
        "expected_pmcid": "PMC12583504",
        "key_concepts": ["KRAS", "mutation", "immune", "suppression", "T cells"],
    },
    {
        "question": "What is the neuro-immune axis in cancer?",
        "expected_pmcid": "PMC12570465",
        "key_concepts": ["neuro-immune", "nervous system", "immune system", "cancer"],
    },
    {
        "question": "What are the latest immunotherapy treatments for lung cancer?",
        "expected_pmcid": "PMC12625643",
        "key_concepts": ["immunotherapy", "lung cancer", "PD-1", "checkpoint inhibitor"],
    },
    {
        "question": "What is the role of CCR8 in tumor microenvironment?",
        "expected_pmcid": "PMC12541881",
        "key_concepts": ["CCR8", "tumor microenvironment", "Treg", "T cells"],
    },
]


# ─────────────────────────────────────────────────────────────
# RAG 시스템
# ─────────────────────────────────────────────────────────────

class EvidenceRAG:
    """Evidence RAG 시스템 (평가용)"""

    def __init__(self):
        self.weaviate_client = weaviate.connect_to_local()
        self.collection = self.weaviate_client.collections.get(COLLECTION_NAME)
        self.embedding_client = EmbeddingClient()
        self.openai_client = OpenAI()

    def retrieve(self, query: str, limit: int = 5, alpha: float = 0.7) -> list[dict]:
        """하이브리드 검색"""
        query_vector = self.embedding_client.embed_text(query)

        results = self.collection.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            return_metadata=MetadataQuery(score=True),
        )

        chunks = []
        for obj in results.objects:
            props = obj.properties
            chunks.append({
                "pmcid": props.get("pmcid", ""),
                "title": props.get("title", ""),
                "section": props.get("section", ""),
                "content": props.get("content", ""),
                "score": obj.metadata.score or 0.0,
            })

        return chunks

    def generate_answer(self, question: str, chunks: list[dict]) -> str:
        """LLM 답변 생성"""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"[{i}] {chunk['title']} ({chunk['section']})\n{chunk['content']}")

        context = "\n\n".join(context_parts)

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a medical research assistant. Answer questions based on the provided research evidence.
Rules:
1. Only use information from the provided context
2. Cite sources using [1], [2], etc. notation
3. If the context doesn't contain relevant information, say so
4. Be concise but thorough"""
                },
                {
                    "role": "user",
                    "content": f"""Context:
{context}

Question: {question}

Please provide a well-structured answer with citations."""
                }
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        return response.choices[0].message.content

    def close(self):
        self.weaviate_client.close()


# ─────────────────────────────────────────────────────────────
# LLM 기반 평가
# ─────────────────────────────────────────────────────────────

def evaluate_faithfulness(openai_client: OpenAI, answer: str, contexts: list[str]) -> float:
    """답변이 컨텍스트에 근거하는지 평가 (0-1)"""
    context_text = "\n\n".join(contexts[:3])  # 처음 3개만 사용

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are an evaluator. Score how faithfully the answer is grounded in the provided context.
Return ONLY a JSON object: {"score": 0.0-1.0, "reason": "brief explanation"}
- 1.0: All claims in the answer are supported by the context
- 0.5: Some claims are supported, some are not
- 0.0: Answer contains claims not found in context (hallucination)"""
            },
            {
                "role": "user",
                "content": f"""Context:
{context_text}

Answer to evaluate:
{answer}

Evaluate faithfulness:"""
            }
        ],
        temperature=0,
        max_tokens=200,
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return result.get("score", 0.5)
    except:
        return 0.5  # 파싱 실패시 기본값


def evaluate_relevancy(openai_client: OpenAI, question: str, answer: str) -> float:
    """답변이 질문에 관련있는지 평가 (0-1)"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are an evaluator. Score how relevant the answer is to the question.
Return ONLY a JSON object: {"score": 0.0-1.0, "reason": "brief explanation"}
- 1.0: Answer directly and completely addresses the question
- 0.5: Answer partially addresses the question
- 0.0: Answer is unrelated to the question"""
            },
            {
                "role": "user",
                "content": f"""Question: {question}

Answer: {answer}

Evaluate relevancy:"""
            }
        ],
        temperature=0,
        max_tokens=200,
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return result.get("score", 0.5)
    except:
        return 0.5


def evaluate_key_concepts(answer: str, key_concepts: list[str]) -> float:
    """답변에 핵심 개념이 포함되어 있는지 평가 (0-1)"""
    answer_lower = answer.lower()
    found = sum(1 for concept in key_concepts if concept.lower() in answer_lower)
    return found / len(key_concepts)


# ─────────────────────────────────────────────────────────────
# 메인 평가 함수
# ─────────────────────────────────────────────────────────────

def run_evaluation():
    """RAG 평가 실행"""
    print("=" * 70)
    print("OAR-11: RAG 시스템 평가")
    print("=" * 70)

    rag = EvidenceRAG()
    openai_client = OpenAI()

    results = []

    try:
        for i, item in enumerate(EVAL_DATASET, 1):
            question = item["question"]
            expected_pmcid = item["expected_pmcid"]
            key_concepts = item["key_concepts"]

            print(f"\n[{i}/{len(EVAL_DATASET)}] {question[:55]}...")

            # 1. 검색
            chunks = rag.retrieve(question, limit=5)
            retrieved_pmcids = [c["pmcid"] for c in chunks]
            contexts = [c["content"] for c in chunks]

            # 검색 정확도
            retrieval_hit = expected_pmcid in retrieved_pmcids
            top1_hit = chunks[0]["pmcid"] == expected_pmcid if chunks else False
            mrr = 0.0
            for j, pmcid in enumerate(retrieved_pmcids, 1):
                if pmcid == expected_pmcid:
                    mrr = 1.0 / j
                    break

            print(f"   검색: {'✅' if retrieval_hit else '❌'} (Top-1: {'✅' if top1_hit else '❌'}, MRR: {mrr:.2f})")

            # 2. 답변 생성
            answer = rag.generate_answer(question, chunks)

            # 3. 평가
            faithfulness_score = evaluate_faithfulness(openai_client, answer, contexts)
            relevancy_score = evaluate_relevancy(openai_client, question, answer)
            concept_score = evaluate_key_concepts(answer, key_concepts)

            print(f"   Faithfulness: {faithfulness_score:.2f} | Relevancy: {relevancy_score:.2f} | Concepts: {concept_score:.2f}")

            results.append({
                "question": question,
                "expected_pmcid": expected_pmcid,
                "retrieval_hit": retrieval_hit,
                "top1_hit": top1_hit,
                "mrr": mrr,
                "faithfulness": faithfulness_score,
                "relevancy": relevancy_score,
                "concept_coverage": concept_score,
            })

        # 종합 결과
        print("\n" + "=" * 70)
        print("📊 평가 결과 요약")
        print("=" * 70)

        n = len(results)

        # 검색 지표
        retrieval_acc = sum(1 for r in results if r["retrieval_hit"]) / n
        top1_acc = sum(1 for r in results if r["top1_hit"]) / n
        avg_mrr = sum(r["mrr"] for r in results) / n

        print("\n📎 검색 품질 (Retrieval)")
        print(f"   Recall@5:     {retrieval_acc:.1%} ({sum(1 for r in results if r['retrieval_hit'])}/{n})")
        print(f"   Precision@1:  {top1_acc:.1%} ({sum(1 for r in results if r['top1_hit'])}/{n})")
        print(f"   MRR:          {avg_mrr:.3f}")

        # 생성 지표
        avg_faithfulness = sum(r["faithfulness"] for r in results) / n
        avg_relevancy = sum(r["relevancy"] for r in results) / n
        avg_concepts = sum(r["concept_coverage"] for r in results) / n

        print("\n📝 생성 품질 (Generation)")
        print(f"   Faithfulness:      {avg_faithfulness:.2f}")
        print(f"   Answer Relevancy:  {avg_relevancy:.2f}")
        print(f"   Concept Coverage:  {avg_concepts:.2f}")

        # 종합 점수
        overall = (retrieval_acc + avg_faithfulness + avg_relevancy + avg_concepts) / 4
        print(f"\n🎯 종합 점수: {overall:.2f}")

        if overall >= 0.8:
            print("   → 우수 ✅")
        elif overall >= 0.6:
            print("   → 양호 👍")
        else:
            print("   → 개선 필요 ⚠️")

        # 결과 저장
        result_path = Path(__file__).parent.parent / "docs" / "evaluation-results.json"
        with open(result_path, "w") as f:
            json.dump({
                "summary": {
                    "retrieval_recall_at_5": retrieval_acc,
                    "retrieval_precision_at_1": top1_acc,
                    "mrr": avg_mrr,
                    "faithfulness": avg_faithfulness,
                    "relevancy": avg_relevancy,
                    "concept_coverage": avg_concepts,
                    "overall": overall,
                },
                "details": results,
            }, f, indent=2)
        print(f"\n결과 저장: {result_path}")

        return results

    finally:
        rag.close()


def run_quick_test():
    """빠른 검색 테스트"""
    print("=" * 70)
    print("OAR-11: 빠른 검색 테스트")
    print("=" * 70)

    rag = EvidenceRAG()

    try:
        for i, item in enumerate(EVAL_DATASET, 1):
            question = item["question"]
            expected_pmcid = item["expected_pmcid"]

            print(f"\n[{i}] {question[:60]}...")

            chunks = rag.retrieve(question, limit=3)

            for j, chunk in enumerate(chunks, 1):
                is_expected = "✅" if chunk["pmcid"] == expected_pmcid else "  "
                print(f"    {is_expected} [{j}] {chunk['pmcid']} ({chunk['section']}) - {chunk['score']:.3f}")

    finally:
        rag.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OAR-11 RAG 평가")
    parser.add_argument("--quick", action="store_true", help="빠른 검색 테스트만 실행")
    args = parser.parse_args()

    if args.quick:
        run_quick_test()
    else:
        run_evaluation()
