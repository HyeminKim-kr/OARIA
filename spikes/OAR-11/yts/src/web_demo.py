"""웹 기반 RAG 챗봇 데모

Gradio를 사용한 대화형 인터페이스
"""

import sys
from pathlib import Path
from dataclasses import dataclass

import gradio as gr
import weaviate
from weaviate.classes.query import MetadataQuery
from openai import OpenAI

# OAR-31 Weaviate 임포트
OAR_31_PATH = Path(__file__).parent.parent.parent.parent / "OAR-31" / "yts" / "src"
sys.path.insert(0, str(OAR_31_PATH))
from schema import COLLECTION_NAME
from embeddings import EmbeddingClient


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

    def get_stats(self) -> dict:
        """저장된 데이터 통계"""
        count = self.collection.aggregate.over_all(total_count=True).total_count
        return {"total_chunks": count}

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
                "source_url": props.get("sourceUrl", ""),
                "offset_start": props.get("offsetStart", 0),
                "offset_end": props.get("offsetEnd", 0),
            })

        return chunks

    def generate_answer(self, question: str, chunks: list[dict], stream: bool = False):
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
4. Be concise but thorough
5. Answer in Korean if the question is in Korean, otherwise in English"""
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
            stream=stream,
        )

        if stream:
            return response  # Return generator
        return response.choices[0].message.content

    def format_evidence_block(self, chunks: list[dict]) -> str:
        """근거 블록 포맷팅 - 답변 아래에 표시할 인용 정보"""
        evidence_parts = []
        for i, chunk in enumerate(chunks, 1):
            # 원문 스니펫 (처음 250자)
            content_preview = chunk['content'][:250].replace('\n', ' ')
            if len(chunk['content']) > 250:
                content_preview += "..."

            url = chunk['source_url'] or f"https://europepmc.org/article/PMC/{chunk['pmcid'].replace('PMC', '')}"

            # offset 정보
            offset_start = chunk.get('offset_start', 0)
            offset_end = chunk.get('offset_end', 0)

            evidence_parts.append(
                f"**[{i}] {chunk['pmcid']}** | `{chunk['section']}` | 관련도: {chunk['score']:.2f}\n"
                f"📍 **원문 위치**: `offset {offset_start:,} ~ {offset_end:,}` ({offset_end - offset_start:,}자)\n\n"
                f"> {content_preview}\n\n"
                f"🔗 [Europe PMC에서 원문 보기]({url})"
            )

        return "\n\n---\n\n".join(evidence_parts)

    def query(self, question: str, top_k: int = 5) -> tuple[str, str]:
        """RAG 쿼리 실행 - (answer, citations) 반환"""
        chunks = self.retrieve(question, limit=top_k)

        if not chunks:
            return "관련 논문을 찾을 수 없습니다.", ""

        answer = self.generate_answer(question, chunks)

        # Citation 포맷팅
        citations = []
        for i, chunk in enumerate(chunks, 1):
            url = chunk['source_url'] or f"https://europepmc.org/article/PMC/{chunk['pmcid'].replace('PMC', '')}"
            citations.append(
                f"**[{i}]** [{chunk['pmcid']}]({url})\n"
                f"  - 제목: {chunk['title'][:60]}...\n"
                f"  - 섹션: {chunk['section']}\n"
                f"  - 관련도: {chunk['score']:.3f}"
            )

        return answer, "\n\n".join(citations)

    def close(self):
        self.weaviate_client.close()


# ─────────────────────────────────────────────────────────────
# Gradio 인터페이스
# ─────────────────────────────────────────────────────────────

# 전역 RAG 인스턴스
rag = None


def initialize_rag():
    """RAG 시스템 초기화"""
    global rag
    if rag is None:
        rag = EvidenceRAG()
    return rag


def chat(message: str, history: list) -> tuple[str, str]:
    """채팅 응답 생성"""
    rag_instance = initialize_rag()
    answer, citations = rag_instance.query(message, top_k=5)
    return answer, citations


def get_system_info() -> str:
    """시스템 정보 반환"""
    rag_instance = initialize_rag()
    stats = rag_instance.get_stats()
    return f"📊 저장된 청크: {stats['total_chunks']}개"


# 샘플 질문들
SAMPLE_QUESTIONS = [
    "What are the latest immunotherapy treatments for lung cancer?",
    "How does KRAS mutation affect immune response in cancer?",
    "What is the role of neutrophils in tumor microenvironment?",
    "폐암 치료에서 PD-1 억제제의 효과는?",
    "CAR-T 치료의 고형암 적용 한계점은?",
]


def create_demo():
    """Gradio 데모 생성"""

    with gr.Blocks(title="OAR-11: Evidence RAG") as demo:

        gr.Markdown("""
        # 🔬 OAR-11: Evidence RAG 시스템

        **의학 논문 기반 질의응답 시스템**

        수집된 암 관련 논문에서 근거를 검색하고, AI가 답변을 생성합니다.
        모든 답변에는 출처(Citation)가 함께 제공됩니다.
        """)

        with gr.Row():
            system_info = gr.Markdown(get_system_info())

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    label="대화",
                    height=400,
                )

                with gr.Row():
                    msg = gr.Textbox(
                        label="질문을 입력하세요",
                        placeholder="예: What is the role of PD-1 in lung cancer immunotherapy?",
                        scale=4,
                    )
                    submit_btn = gr.Button("전송", variant="primary", scale=1)

                with gr.Row():
                    clear_btn = gr.Button("대화 초기화")

            with gr.Column(scale=1):
                gr.Markdown("### 📚 인용 문헌")
                citations_box = gr.Markdown(
                    value="*질문을 입력하면 관련 논문이 표시됩니다.*",
                )

        gr.Markdown("### 💡 샘플 질문")
        with gr.Row():
            for q in SAMPLE_QUESTIONS[:3]:
                gr.Button(q[:40] + "...", size="sm").click(
                    lambda x=q: x, outputs=msg
                )
        with gr.Row():
            for q in SAMPLE_QUESTIONS[3:]:
                gr.Button(q[:40] + "...", size="sm").click(
                    lambda x=q: x, outputs=msg
                )

        # 이벤트 핸들러 (스트리밍)
        def respond_stream(message, chat_history):
            if not message.strip():
                yield chat_history, "*질문을 입력해주세요*"
                return

            rag_instance = initialize_rag()

            # 1. 검색
            chunks = rag_instance.retrieve(message, limit=5)

            if not chunks:
                chat_history.append({"role": "user", "content": message})
                chat_history.append({"role": "assistant", "content": "관련 논문을 찾을 수 없습니다."})
                yield chat_history, ""
                return

            # 근거 블록 생성 (답변 아래에 붙일 내용)
            evidence_block = rag_instance.format_evidence_block(chunks)

            # 우측 패널용 요약
            citations_summary = f"**검색된 논문: {len(chunks)}개**\n\n"
            for i, chunk in enumerate(chunks, 1):
                citations_summary += f"[{i}] {chunk['pmcid']} ({chunk['section']}) - {chunk['score']:.2f}\n"

            # 2. 사용자 메시지 추가
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": ""})

            # 3. 스트리밍 답변 생성
            stream = rag_instance.generate_answer(message, chunks, stream=True)
            answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    answer += chunk.choices[0].delta.content
                    chat_history[-1]["content"] = answer
                    yield chat_history, citations_summary

            # 4. 답변 완료 후 근거 블록 추가
            final_response = f"{answer}\n\n---\n\n### 📚 참고 근거\n\n{evidence_block}"
            chat_history[-1]["content"] = final_response
            yield chat_history, citations_summary

        submit_btn.click(
            respond_stream,
            inputs=[msg, chatbot],
            outputs=[chatbot, citations_box],
        ).then(
            lambda: "", outputs=msg
        )

        msg.submit(
            respond_stream,
            inputs=[msg, chatbot],
            outputs=[chatbot, citations_box],
        ).then(
            lambda: "", outputs=msg
        )

        clear_btn.click(
            lambda: ([], "*질문을 입력하면 관련 논문이 표시됩니다.*"),
            outputs=[chatbot, citations_box],
        )

        gr.Markdown("""
        ---
        **기술 스택**: Weaviate (Vector DB) + OpenAI Embeddings + GPT-4o-mini

        *OAR-11 Evidence RAG 시스템 - E2E 데모*
        """)

    return demo


if __name__ == "__main__":
    demo = create_demo()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
