"""RAG 데모: 질문 → 검색 → LLM 답변 + Citation

E2E 데모용 간단 RAG 시스템
"""

import sys
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
# 데이터 모델
# ─────────────────────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    """검색된 청크"""
    chunk_id: str
    paper_id: str
    pmcid: str
    title: str
    section: str
    content: str
    score: float
    source_url: str
    offset_start: int
    offset_end: int


@dataclass
class Citation:
    """인용 정보"""
    index: int  # [1], [2], ...
    pmcid: str
    title: str
    section: str
    content_preview: str  # 50자 미리보기
    source_url: str


@dataclass
class RAGResponse:
    """RAG 응답"""
    question: str
    answer: str
    citations: list[Citation]
    chunks_used: int


# ─────────────────────────────────────────────────────────────
# RAG 시스템
# ─────────────────────────────────────────────────────────────

class EvidenceRAG:
    """Evidence RAG 시스템"""

    def __init__(self):
        self.weaviate_client = weaviate.connect_to_local()
        self.collection = self.weaviate_client.collections.get(COLLECTION_NAME)
        self.embedding_client = EmbeddingClient()
        self.openai_client = OpenAI()

    def close(self):
        self.weaviate_client.close()

    def retrieve(self, query: str, limit: int = 5, alpha: float = 0.7) -> list[RetrievedChunk]:
        """하이브리드 검색으로 관련 청크 검색

        Args:
            query: 검색 쿼리
            limit: 최대 결과 수
            alpha: 벡터 vs 키워드 가중치 (1.0 = 벡터만, 0.0 = 키워드만)
        """
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
            chunks.append(RetrievedChunk(
                chunk_id=props.get("chunkId", ""),
                paper_id=props.get("paperId", ""),
                pmcid=props.get("pmcid", ""),
                title=props.get("title", ""),
                section=props.get("section", ""),
                content=props.get("content", ""),
                score=obj.metadata.score or 0.0,
                source_url=props.get("sourceUrl", ""),
                offset_start=props.get("offsetStart", 0),
                offset_end=props.get("offsetEnd", 0),
            ))

        return chunks

    def generate_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        """검색된 청크를 기반으로 LLM 답변 생성"""
        # 컨텍스트 구성
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"[{i}] {chunk.title} ({chunk.section})\n{chunk.content}")

        context = "\n\n".join(context_parts)

        # LLM 호출
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
4. Be concise but thorough
5. Use scientific terminology appropriately"""
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

    def create_citations(self, chunks: list[RetrievedChunk]) -> list[Citation]:
        """청크에서 인용 정보 생성"""
        citations = []
        for i, chunk in enumerate(chunks, 1):
            preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
            citations.append(Citation(
                index=i,
                pmcid=chunk.pmcid,
                title=chunk.title,
                section=chunk.section,
                content_preview=preview,
                source_url=chunk.source_url,
            ))
        return citations

    def query(self, question: str, top_k: int = 5) -> RAGResponse:
        """RAG 쿼리 실행"""
        # 1. 검색
        chunks = self.retrieve(question, limit=top_k)

        if not chunks:
            return RAGResponse(
                question=question,
                answer="No relevant evidence found in the database.",
                citations=[],
                chunks_used=0,
            )

        # 2. 답변 생성
        answer = self.generate_answer(question, chunks)

        # 3. 인용 정보 생성
        citations = self.create_citations(chunks)

        return RAGResponse(
            question=question,
            answer=answer,
            citations=citations,
            chunks_used=len(chunks),
        )


# ─────────────────────────────────────────────────────────────
# 데모 실행
# ─────────────────────────────────────────────────────────────

def run_demo():
    """RAG 데모 실행"""
    print("=" * 70)
    print("OAR-11: Evidence RAG 데모")
    print("=" * 70)

    # 샘플 질문들
    sample_questions = [
        "What are the latest immunotherapy treatments for lung cancer?",
        "How effective are PD-1 inhibitors in non-small cell lung cancer?",
        "What challenges exist for CAR-T therapy in solid tumors?",
    ]

    rag = EvidenceRAG()
    try:
        # 현재 저장된 청크 수 확인
        count = rag.collection.aggregate.over_all(total_count=True).total_count
        print(f"\n📊 저장된 청크: {count}개")

        if count == 0:
            print("\n⚠️ 저장된 청크가 없습니다. 먼저 ingest.py를 실행하세요.")
            return

        for i, question in enumerate(sample_questions, 1):
            print(f"\n{'─' * 70}")
            print(f"질문 {i}: {question}")
            print("─" * 70)

            # RAG 쿼리
            response = rag.query(question, top_k=3)

            # 답변 출력
            print(f"\n📝 답변:\n{response.answer}")

            # 인용 출력
            print(f"\n📚 인용 ({response.chunks_used}개 청크 사용):")
            for citation in response.citations:
                print(f"   [{citation.index}] {citation.pmcid}: {citation.title[:40]}...")
                print(f"       섹션: {citation.section}")
                print(f"       미리보기: {citation.content_preview[:60]}...")
                print(f"       URL: {citation.source_url}")

    finally:
        rag.close()

    print("\n" + "=" * 70)
    print("✅ RAG 데모 완료!")
    print("=" * 70)


def interactive_demo():
    """대화형 RAG 데모"""
    print("=" * 70)
    print("OAR-11: Evidence RAG (대화형 모드)")
    print("=" * 70)
    print("\n'quit' 또는 'exit'를 입력하면 종료됩니다.\n")

    rag = EvidenceRAG()
    try:
        count = rag.collection.aggregate.over_all(total_count=True).total_count
        print(f"📊 저장된 청크: {count}개\n")

        while True:
            question = input("질문: ").strip()
            if question.lower() in ("quit", "exit", "q"):
                break
            if not question:
                continue

            print("\n🔍 검색 중...")
            response = rag.query(question, top_k=5)

            print(f"\n📝 답변:\n{response.answer}\n")

            print(f"📚 인용:")
            for citation in response.citations:
                print(f"   [{citation.index}] {citation.pmcid} - {citation.section}")
            print()

    finally:
        rag.close()

    print("👋 종료됨")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", "-i", action="store_true", help="대화형 모드")
    args = parser.parse_args()

    if args.interactive:
        interactive_demo()
    else:
        run_demo()
