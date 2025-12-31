"""RAGAS 기반 RAG 시스템 평가

자동화된 RAG 품질 평가:
- Faithfulness: 답변이 컨텍스트에 근거하는지
- Answer Relevancy: 답변이 질문에 관련있는지
- Context Precision: 검색된 문서의 정밀도
- Context Recall: 필요한 정보를 모두 검색했는지
"""

import sys
from pathlib import Path
from dataclasses import dataclass
import json

import weaviate
from weaviate.classes.query import MetadataQuery
from openai import OpenAI
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

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
        "ground_truth": "Neutrophils play a complex role in lung cancer immunotherapy. They can have both pro-tumor and anti-tumor effects. Tumor-associated neutrophils (TANs) can suppress immune responses and promote tumor growth, but they can also be reprogrammed to enhance anti-tumor immunity when combined with PD-1/PD-L1 inhibitors.",
        "expected_pmcid": "PMC12625643",
    },
    {
        "question": "How does KRAS mutation affect immune response in cancer?",
        "ground_truth": "KRAS mutations drive immune suppression through immune-related regulatory networks. Oncogenic KRAS activates signaling pathways that create an immunosuppressive tumor microenvironment, reducing the effectiveness of immune checkpoint inhibitors.",
        "expected_pmcid": "PMC12583504",
    },
    {
        "question": "What is the neuro-immune axis in cancer?",
        "ground_truth": "The neuro-immune axis refers to the bidirectional communication between the nervous system and immune system in cancer. This axis influences tumor progression, immune surveillance, and responses to therapy. Targeting the neuro-immune axis represents a therapeutic opportunity for cancer treatment.",
        "expected_pmcid": "PMC12570465",
    },
    {
        "question": "What are the latest immunotherapy treatments for lung cancer?",
        "ground_truth": "Latest immunotherapy treatments for lung cancer include PD-1/PD-L1 checkpoint inhibitors, bifunctional fusion proteins like M7824 targeting both PD-L1 and TGF-β, combination therapies with anti-CXCL5 and anti-PD-L1, CXCR2 antagonists like SX-682, and CCR8 monoclonal antibodies like BAY 3375968.",
        "expected_pmcid": "PMC12625643",
    },
    {
        "question": "What is the role of CCR8 in tumor microenvironment?",
        "ground_truth": "CCR8 is a chemokine receptor highly expressed on regulatory T cells (Tregs) in the tumor microenvironment. CCR8+ Tregs suppress anti-tumor immunity. Targeting CCR8 with monoclonal antibodies can deplete tumor-infiltrating Tregs and enhance anti-tumor immune responses.",
        "expected_pmcid": "PMC12541881",
    },
]


# ─────────────────────────────────────────────────────────────
# RAG 시스템 (평가용)
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
            max_tokens=1500,
        )

        return response.choices[0].message.content

    def close(self):
        self.weaviate_client.close()


# ─────────────────────────────────────────────────────────────
# RAGAS 평가
# ─────────────────────────────────────────────────────────────

def run_ragas_evaluation():
    """RAGAS 평가 실행"""
    print("=" * 60)
    print("OAR-11: RAGAS 평가")
    print("=" * 60)

    rag = EvidenceRAG()

    # 평가 데이터 수집
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    retrieval_results = []

    try:
        for i, item in enumerate(EVAL_DATASET, 1):
            question = item["question"]
            ground_truth = item["ground_truth"]
            expected_pmcid = item["expected_pmcid"]

            print(f"\n[{i}/{len(EVAL_DATASET)}] 질문: {question[:50]}...")

            # 검색
            chunks = rag.retrieve(question, limit=5)
            context_texts = [c["content"] for c in chunks]
            retrieved_pmcids = [c["pmcid"] for c in chunks]

            # 답변 생성
            answer = rag.generate_answer(question, chunks)

            # 검색 정확도 확인
            found_expected = expected_pmcid in retrieved_pmcids
            print(f"   예상 논문({expected_pmcid}) 검색: {'✅' if found_expected else '❌'}")

            questions.append(question)
            answers.append(answer)
            contexts.append(context_texts)
            ground_truths.append(ground_truth)
            retrieval_results.append({
                "expected": expected_pmcid,
                "retrieved": retrieved_pmcids,
                "found": found_expected,
            })

        # RAGAS Dataset 생성
        eval_data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
        dataset = Dataset.from_dict(eval_data)

        print("\n" + "=" * 60)
        print("RAGAS 평가 실행 중...")
        print("=" * 60)

        # RAGAS 평가 실행
        result = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
        )

        # 결과 출력
        print("\n" + "=" * 60)
        print("📊 RAGAS 평가 결과")
        print("=" * 60)

        for metric, score in result.items():
            emoji = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
            print(f"  {emoji} {metric}: {score:.4f}")

        # 검색 정확도
        print("\n" + "-" * 60)
        print("📎 검색 정확도 (예상 논문 검색 여부)")
        print("-" * 60)

        retrieval_accuracy = sum(1 for r in retrieval_results if r["found"]) / len(retrieval_results)
        print(f"  정확도: {retrieval_accuracy:.1%} ({sum(1 for r in retrieval_results if r['found'])}/{len(retrieval_results)})")

        for i, r in enumerate(retrieval_results, 1):
            status = "✅" if r["found"] else "❌"
            print(f"  [{i}] {status} {r['expected']} → {r['retrieved'][:3]}")

        # 결과 저장
        result_path = Path(__file__).parent.parent / "docs" / "ragas-results.json"
        with open(result_path, "w") as f:
            json.dump({
                "metrics": {k: float(v) for k, v in result.items()},
                "retrieval_accuracy": retrieval_accuracy,
                "details": retrieval_results,
            }, f, indent=2)
        print(f"\n결과 저장: {result_path}")

        # 종합 평가
        print("\n" + "=" * 60)
        print("📋 종합 평가")
        print("=" * 60)

        avg_score = sum(result.values()) / len(result)
        if avg_score >= 0.8:
            print(f"  🎉 우수 (평균: {avg_score:.2f})")
        elif avg_score >= 0.6:
            print(f"  👍 양호 (평균: {avg_score:.2f})")
        else:
            print(f"  ⚠️ 개선 필요 (평균: {avg_score:.2f})")

        return result

    finally:
        rag.close()


def run_quick_test():
    """빠른 검색 테스트 (RAGAS 없이)"""
    print("=" * 60)
    print("OAR-11: 빠른 검색 테스트")
    print("=" * 60)

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

    parser = argparse.ArgumentParser(description="OAR-11 RAGAS 평가")
    parser.add_argument("--quick", action="store_true", help="빠른 검색 테스트만 실행")
    args = parser.parse_args()

    if args.quick:
        run_quick_test()
    else:
        run_ragas_evaluation()
