"""논문별 채팅 라우터

논문 상세 페이지에서 특정 논문에 대한 질의응답 API.
기존 /ai/ask와 달리:
- 단일 논문 필터링 (paper_id 기반)
- Gate 1 도메인 분류 미적용 (이미 논문 컨텍스트 내)
- 더 단순한 RAG 파이프라인 사용
- 대화형 프롬프트 사용 (단일 논문 맥락)

엔드포인트:
- POST /ai/papers/{paper_id}/ask - 논문별 질의응답 (SSE)
- GET /ai/papers/{paper_id}/conversations - 논문별 대화 목록
- POST /ai/papers/{paper_id}/summarize - 요약 생성
- POST /ai/papers/{paper_id}/citation - 인용 정보 생성
"""

import asyncio
import json
import logging
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 논문 전용 대화형 프롬프트
# ─────────────────────────────────────────────────────────────

PAPER_CHAT_PROMPT = """당신은 논문 내용을 설명해주는 친절한 연구 도우미입니다.
사용자가 현재 보고 있는 논문에 대해 질문하면, 마치 옆에서 설명해주듯 자연스럽게 답변합니다.

## 핵심 규칙
1. 이 논문의 내용만을 기반으로 답변
2. 마크다운 헤더(###) 사용 금지 - 자연스러운 문장으로
3. "이 논문에서는", "여기서는" 같은 표현 사용
4. 다른 논문과 비교하지 않음

## 답변 방식
- 먼저 핵심을 간단히 답하고
- 필요하면 부연 설명 추가
- 논문의 어느 부분에서 나온 내용인지 자연스럽게 언급
  (예: "Methods 부분을 보면...", "Results에 따르면...")

## 출처 표기
- 인용 번호 [1], [2] 대신 섹션명으로 자연스럽게 언급
- 예: "Abstract에서 언급했듯이...", "Discussion 부분에서..."

## 추천 질문 (선택적)
사용자가 더 궁금해할 만한 질문이 있다면 마지막에:
```suggestions
- 질문1?
- 질문2?
- 질문3?
```

---
[논문: {paper_title}]

{context}
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.dependencies import CurrentUser
from app.models import Conversation, Message, AnswerLog, Paper, PaperSummary
from app.schemas.chat import Reference, MessageResponse, PaginatedMessages
from app.config import settings
from app.schemas.paper_chat import (
    PaperAskRequest,
    PaperConversationListItem,
    PaginatedPaperConversations,
    SummarizeRequest,
    SummarizeResponse,
    CitationRequest,
    CitationResponse,
)
from app.services.paper_rag_service import paper_rag_service
from app.services.llm_service import llm_service
from app.services.citation_service import citation_service
from app.services.summary_service import summary_service
from app.services.question_classifier_service import question_classifier


router = APIRouter(prefix="/ai/papers", tags=["paper-chat"])


# ─────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────


async def get_paper_or_404(
    paper_id: UUID,
    db: AsyncSession,
) -> Paper:
    """논문 조회 (없으면 404)"""
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found",
        )
    return paper


# ─────────────────────────────────────────────────────────────
# Ask API (SSE Streaming)
# ─────────────────────────────────────────────────────────────


@router.post("/{paper_id}/ask")
async def ask_paper(
    paper_id: UUID,
    request: PaperAskRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """논문별 질의응답 (SSE 스트리밍)

    특정 논문 내에서만 검색하여 질문에 답변합니다.

    Args:
        paper_id: 논문 UUID
        request: 질문 요청

    Returns:
        SSE 스트림:
        - event: status (진행 상태)
        - event: token (LLM 응답 토큰)
        - event: references (검색된 참조)
        - event: done (완료, conversation_id 포함)
    """
    # 논문 존재 확인
    paper = await get_paper_or_404(paper_id, db)

    # 기존 대화 검증
    conversation = None
    if request.conversation_id:
        conversation = await db.get(Conversation, request.conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        # 대화가 해당 논문에 속하는지 확인
        if conversation.paper_id != paper_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation does not belong to this paper",
            )

    async def generate_sse():
        """SSE 스트림 생성"""
        nonlocal conversation
        total_start = time.perf_counter()

        logger.info(f"[PaperChat] Starting SSE for paper={paper.paper_id}, question='{request.question[:50]}...'")

        # 0. 질문 유형 분류
        classify_start = time.perf_counter()
        q_type, q_confidence = await question_classifier.classify(request.question)
        strategy = question_classifier.get_strategy(q_type)
        classify_ms = int((time.perf_counter() - classify_start) * 1000)
        logger.info(f"[PaperChat] Classification: {q_type.value} (confidence={q_confidence:.2f}) in {classify_ms}ms")

        # 분류 결과 SSE 전송
        yield {
            "event": "classification",
            "data": json.dumps({
                "type": q_type.value,
                "confidence": q_confidence,
                "strategy": {
                    "use_reranker": strategy.use_reranker,
                    "top_k": strategy.top_k,
                    "sections": strategy.sections,
                },
            }, ensure_ascii=False),
        }

        # Status: 검색 시작
        yield {
            "event": "status",
            "data": json.dumps({"status": "searching", "message": "논문에서 관련 내용을 검색 중..."}, ensure_ascii=False),
        }

        # 1. RAG 검색 (질문 유형별 전략 적용)
        rag_start = time.perf_counter()
        try:
            if request.include_related:
                # 관련 논문 ID 가져오기 (벡터 유사도 기반)
                from app.services.similar_papers_service import similar_papers_service
                similar_papers = await similar_papers_service.get_vector_similar(
                    paper_id=paper.paper_id,
                    limit=3,
                )
                # paper_id 형식으로 변환 (pmc:PMC12345678)
                related_ids = [
                    f"pmc:{sp.pmcid}" for sp in similar_papers if sp.pmcid
                ]
                logger.info(f"[PaperChat] include_related: found {len(related_ids)} similar papers")

                result = await paper_rag_service.retrieve_with_related(
                    paper_id=paper.paper_id,
                    related_paper_ids=related_ids,
                    query=request.question,
                    use_reranker=strategy.use_reranker,
                    min_score=strategy.min_rerank_score,
                )
            else:
                result = await paper_rag_service.retrieve_from_paper(
                    paper_id=paper.paper_id,
                    query=request.question,
                    sections=strategy.sections,
                    use_reranker=strategy.use_reranker,
                    min_score=strategy.min_rerank_score,
                )
            rag_ms = int((time.perf_counter() - rag_start) * 1000)
            logger.info(f"[PaperChat] RAG completed in {rag_ms}ms, refs={len(result.references)}, context_len={len(result.context)}")
        except Exception as e:
            rag_ms = int((time.perf_counter() - rag_start) * 1000)
            logger.exception(f"[PaperChat] RAG failed after {rag_ms}ms: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": f"검색 중 오류가 발생했습니다: {str(e)}"}, ensure_ascii=False),
            }
            return

        # 2. Status: 응답 생성 중
        yield {
            "event": "status",
            "data": json.dumps({"status": "generating", "message": "답변을 생성 중..."}, ensure_ascii=False),
        }

        # 3. LLM 스트리밍 응답 (논문 전용 프롬프트 사용)
        llm_start = time.perf_counter()
        full_response = ""
        token_count = 0
        first_token_received = False

        # 논문 제목으로 프롬프트 구성
        paper_prompt = PAPER_CHAT_PROMPT.format(
            paper_title=paper.title or paper.paper_id,
            context=result.context,
        )

        try:
            async for chunk in llm_service.generate_stream(
                question=request.question,
                context=result.context,
                references=result.references,
                system_prompt=paper_prompt,
            ):
                if not first_token_received:
                    first_token_ms = int((time.perf_counter() - llm_start) * 1000)
                    logger.info(f"[PaperChat] First token received in {first_token_ms}ms")
                    first_token_received = True

                if chunk.is_done:
                    if chunk.usage:
                        token_count = chunk.usage.get("total_tokens", 0)
                    break

                full_response += chunk.token
                yield {
                    "event": "token",
                    "data": json.dumps({"token": chunk.token}, ensure_ascii=False),
                }
            llm_ms = int((time.perf_counter() - llm_start) * 1000)
            logger.info(f"[PaperChat] LLM completed in {llm_ms}ms, tokens={token_count}, response_len={len(full_response)}")
        except Exception as e:
            llm_ms = int((time.perf_counter() - llm_start) * 1000)
            logger.exception(f"[PaperChat] LLM failed after {llm_ms}ms: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": f"응답 생성 중 오류가 발생했습니다: {str(e)}"}, ensure_ascii=False),
            }
            return

        # 4. References 전송
        references_data = [ref.model_dump() for ref in result.references]
        yield {
            "event": "references",
            "data": json.dumps({"references": references_data}, ensure_ascii=False),
        }

        # 5. 완료 로깅
        total_ms = int((time.perf_counter() - total_start) * 1000)
        logger.info(f"[PaperChat] Completed in {total_ms}ms (RAG={rag_ms}, LLM={llm_ms})")

        # 6. Done 이벤트 (대화 저장 비활성화 - 요약 캐싱 시스템 도입에 따름)
        yield {
            "event": "done",
            "data": json.dumps({
                "status": "completed",
                "latency_ms": total_ms,
            }, ensure_ascii=False),
        }

    return EventSourceResponse(generate_sse())


# ─────────────────────────────────────────────────────────────
# Conversation API
# ─────────────────────────────────────────────────────────────


@router.get("/{paper_id}/conversations")
async def get_paper_conversations(
    paper_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
) -> PaginatedPaperConversations:
    """논문별 대화 목록 조회"""
    # 논문 존재 확인
    await get_paper_or_404(paper_id, db)

    # 총 개수
    count_stmt = (
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.paper_id == paper_id,
            Conversation.conversation_type == "paper",
            Conversation.status != "deleted",
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # 대화 목록
    offset = (page - 1) * size
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.paper_id == paper_id,
            Conversation.conversation_type == "paper",
            Conversation.status != "deleted",
        )
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    items = [
        PaperConversationListItem(
            id=conv.id,
            title=conv.title,
            message_count=conv.message_count,
            last_message_at=conv.last_message_at,
            last_message_preview=None,  # TODO: 마지막 메시지 미리보기
        )
        for conv in conversations
    ]

    return PaginatedPaperConversations(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{paper_id}/conversations/{conversation_id}/messages")
async def get_paper_conversation_messages(
    paper_id: UUID,
    conversation_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> PaginatedMessages:
    """논문별 대화 메시지 조회"""
    # 대화 검증
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    if conversation.paper_id != paper_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation does not belong to this paper",
        )

    # 총 개수
    count_stmt = (
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # 메시지 목록
    offset = (page - 1) * size
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # assistant 메시지에 references 추가
    items = []
    for msg in messages:
        references = None
        if msg.role == "assistant" and msg.answer_log:
            references = [
                Reference(**ref) for ref in (msg.answer_log.evidence or [])
            ]

        items.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            tokens_used=msg.tokens_used,
            model=msg.model,
            latency_ms=msg.latency_ms,
            created_at=msg.created_at,
            references=references,
        ))

    return PaginatedMessages(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


# ─────────────────────────────────────────────────────────────
# Summary API
# ─────────────────────────────────────────────────────────────


@router.post("/{paper_id}/summarize")
async def summarize_paper(
    paper_id: UUID,
    request: SummarizeRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """논문 요약 생성 (캐싱 지원)

    Args:
        paper_id: 논문 UUID
        request: 요약 요청 (type, stream)

    Returns:
        요약 결과 또는 SSE 스트림

    캐싱 동작:
        1. DB에서 캐시된 요약 확인
        2. 캐시 있으면 → 스트리밍 반환 (타이핑 효과)
        3. 캐시 없으면 → LLM 생성 → DB 저장 → 백그라운드 임베딩 트리거
    """
    paper = await get_paper_or_404(paper_id, db)

    # 캐시된 요약 확인
    cached_result = await db.execute(
        select(PaperSummary)
        .where(PaperSummary.paper_id == paper_id)
        .where(PaperSummary.summary_type == request.type)
    )
    cached_summary = cached_result.scalar_one_or_none()

    if request.stream:
        async def generate_sse():
            if cached_summary:
                # 캐시된 요약을 스트리밍으로 반환 (타이핑 효과)
                logger.info(f"[Summarize] Cache hit for paper={paper.paper_id}, type={request.type}")

                # 여러 단어씩 묶어서 스트리밍 (자연스러운 타이핑 효과)
                words = cached_summary.summary.split(' ')
                chunk_size = 4  # 4단어씩 묶기
                for i in range(0, len(words), chunk_size):
                    chunk_words = words[i:i + chunk_size]
                    token = ' '.join(chunk_words)
                    # 마지막 청크가 아니면 공백 추가
                    if i + chunk_size < len(words):
                        token += ' '
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": token}, ensure_ascii=False),
                    }
                    # 타이핑 효과를 위한 딜레이 (70ms)
                    await asyncio.sleep(0.07)

                yield {
                    "event": "done",
                    "data": json.dumps({
                        "status": "completed",
                        "cached": True,
                        "summary_id": str(cached_summary.id),
                    }, ensure_ascii=False),
                }
            else:
                # 새 요약 생성 및 스트리밍
                logger.info(f"[Summarize] Cache miss for paper={paper.paper_id}, type={request.type}, generating...")

                full_response = ""
                tokens_used = 0
                sections_used = []

                async for chunk in summary_service.generate_summary_stream(
                    paper=paper,
                    summary_type=request.type,
                ):
                    full_response += chunk
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": chunk}, ensure_ascii=False),
                    }

                # DB에 요약 저장
                new_summary = PaperSummary(
                    paper_id=paper_id,
                    summary_type=request.type,
                    summary=full_response,
                    sections_used=sections_used or None,
                    tokens_used=tokens_used or None,
                    embedding_status="pending",
                )
                db.add(new_summary)
                await db.commit()
                await db.refresh(new_summary)

                logger.info(f"[Summarize] Saved summary id={new_summary.id}, triggering embed task...")

                # 백그라운드 임베딩 태스크 트리거
                try:
                    _trigger_embed_summary_task(str(new_summary.id))
                except Exception as e:
                    logger.warning(f"[Summarize] Failed to trigger embed task: {e}")

                yield {
                    "event": "done",
                    "data": json.dumps({
                        "status": "completed",
                        "cached": False,
                        "summary_id": str(new_summary.id),
                    }, ensure_ascii=False),
                }

        return EventSourceResponse(generate_sse())
    else:
        # 일반 응답 (non-streaming)
        if cached_summary:
            logger.info(f"[Summarize] Cache hit (non-stream) for paper={paper.paper_id}")
            return SummarizeResponse(
                paper_id=paper.paper_id,
                summary_type=cached_summary.summary_type,
                summary=cached_summary.summary,
                sections_used=cached_summary.sections_used,
                tokens_used=cached_summary.tokens_used,
                latency_ms=0,  # 캐시이므로 0
            )

        # 새 요약 생성
        result = await summary_service.generate_summary(
            paper=paper,
            summary_type=request.type,
        )

        # DB에 저장
        new_summary = PaperSummary(
            paper_id=paper_id,
            summary_type=request.type,
            summary=result.summary,
            sections_used=result.sections_used,
            tokens_used=result.tokens_used,
            embedding_status="pending",
        )
        db.add(new_summary)
        await db.commit()
        await db.refresh(new_summary)

        # 백그라운드 임베딩 태스크 트리거
        try:
            _trigger_embed_summary_task(str(new_summary.id))
        except Exception as e:
            logger.warning(f"[Summarize] Failed to trigger embed task: {e}")

        return SummarizeResponse(
            paper_id=paper.paper_id,
            summary_type=result.summary_type,
            summary=result.summary,
            sections_used=result.sections_used,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
        )


def _trigger_embed_summary_task(summary_id: str) -> None:
    """백그라운드 요약 임베딩 태스크 트리거

    Args:
        summary_id: PaperSummary.id (UUID string)
    """
    from celery import Celery

    redis_url = settings.redis_url

    celery_app = Celery(
        "oaria_batch",
        broker=redis_url,
        backend=redis_url,
    )

    celery_app.send_task(
        "src.tasks.embed_summary.embed_summary_task",
        args=[summary_id],
        queue="embed",
    )

    logger.info(f"[Summarize] Triggered embed_summary_task for summary_id={summary_id}")


# ─────────────────────────────────────────────────────────────
# Citation API
# ─────────────────────────────────────────────────────────────


@router.post("/{paper_id}/citation")
async def get_paper_citation(
    paper_id: UUID,
    request: CitationRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CitationResponse:
    """인용 정보 생성

    Args:
        paper_id: 논문 UUID
        request: 인용 형식 요청

    Returns:
        인용 정보
    """
    from sqlalchemy.orm import selectinload

    # authors 관계를 미리 로드 (lazy loading 방지)
    stmt = select(Paper).where(Paper.id == paper_id).options(selectinload(Paper.authors))
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found",
        )

    citation_result = citation_service.generate(
        paper=paper,
        format=request.format,
    )

    return CitationResponse(
        paper_id=citation_result.paper_id,
        format=citation_result.format,
        citation=citation_result.citation,
    )
