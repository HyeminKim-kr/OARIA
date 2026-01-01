"""AI 라우터

Ask AI 엔드포인트 (SSE 스트리밍)
대화 CRUD 엔드포인트
"""

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models import Conversation, Message, AnswerLog
from app.schemas.chat import (
    AskRequest,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListItem,
    MessageResponse,
    PaginatedConversations,
    PaginatedMessages,
)
from app.services import rag_service, llm_service


router = APIRouter(prefix="/ai", tags=["ai"])


# ─────────────────────────────────────────────────────────────
# Ask AI (SSE Streaming)
# ─────────────────────────────────────────────────────────────


@router.post("/ask")
async def ask_ai(
    request: AskRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """AI에게 질문하기 (SSE 스트리밍)

    Returns:
        SSE 스트림:
        - event: references (검색된 참조 문헌)
        - event: token (LLM 응답 토큰)
        - event: done (완료, conversation_id 포함)
    """
    import time

    total_start = time.perf_counter()

    # 1. RAG 검색
    filters = request.filters or {}
    retrieval_result = rag_service.retrieve(
        query=request.question,
        year_from=filters.year_from if hasattr(filters, "year_from") else None,
        year_to=filters.year_to if hasattr(filters, "year_to") else None,
        sections=filters.sections if hasattr(filters, "sections") else None,
    )

    # 2. 대화 생성 또는 조회
    if request.conversation_id:
        conversation = await db.get(Conversation, request.conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        # 새 대화 생성 (제목은 첫 질문에서 자동 생성)
        title = request.question[:50] + "..." if len(request.question) > 50 else request.question
        conversation = Conversation(
            user_id=current_user.id,
            title=title,
        )
        db.add(conversation)
        await db.flush()

    # 3. 사용자 메시지 저장
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.question,
    )
    db.add(user_message)
    await db.flush()

    async def generate_sse():
        """SSE 스트림 생성"""
        nonlocal conversation

        # References 이벤트 전송
        references_data = [ref.model_dump() for ref in retrieval_result.references]
        yield f"event: references\ndata: {json.dumps({'references': references_data}, ensure_ascii=False)}\n\n"

        # LLM 스트리밍 응답
        full_content = ""
        usage = None

        for chunk in llm_service.generate_stream(
            question=request.question,
            context=retrieval_result.context,
            references=retrieval_result.references,
        ):
            if chunk.is_done:
                usage = chunk.usage
            elif chunk.token:
                full_content += chunk.token
                yield f"event: token\ndata: {json.dumps({'token': chunk.token}, ensure_ascii=False)}\n\n"

        # Assistant 메시지 저장
        total_latency = int((time.perf_counter() - total_start) * 1000)

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=full_content,
            tokens_used=usage.get("total_tokens") if usage else None,
            model=llm_service._get_client() and "gpt-4o-mini" or "mock",
            latency_ms=total_latency,
        )
        db.add(assistant_message)
        await db.flush()

        # Answer Log 저장
        evidence_data = [ref.model_dump() for ref in retrieval_result.references]
        answer_log = AnswerLog(
            message_id=assistant_message.id,
            conversation_id=conversation.id,
            user_id=current_user.id,
            question=request.question,
            answer=full_content,
            search_query=request.question,
            search_filters=request.filters.model_dump() if request.filters else None,
            evidence=evidence_data,
            model="gpt-4o-mini" if not llm_service.use_mock else "mock",
            prompt_tokens=usage.get("prompt_tokens") if usage else None,
            completion_tokens=usage.get("completion_tokens") if usage else None,
            total_tokens=usage.get("total_tokens") if usage else None,
            search_latency_ms=retrieval_result.search_latency_ms,
            llm_latency_ms=total_latency - retrieval_result.search_latency_ms,
            total_latency_ms=total_latency,
        )
        db.add(answer_log)
        await db.commit()

        # Done 이벤트 전송
        done_data = {
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_message.id),
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────
# Conversations CRUD
# ─────────────────────────────────────────────────────────────


@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    size: int = 20,
):
    """대화 목록 조회"""
    offset = (page - 1) * size

    # 총 개수
    count_query = select(func.count()).select_from(Conversation).where(
        Conversation.user_id == current_user.id,
        Conversation.status == "active",
    )
    total = (await db.execute(count_query)).scalar() or 0

    # 대화 목록
    query = (
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.status == "active",
        )
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()

    items = [
        ConversationListItem(
            id=c.id,
            title=c.title,
            status=c.status,
            message_count=c.message_count,
            last_message_at=c.last_message_at,
        )
        for c in conversations
    ]

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedConversations(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """대화 상세 조회"""
    conversation = await db.get(Conversation, conversation_id)

    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    update: ConversationUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """대화 수정 (제목, 상태)"""
    conversation = await db.get(Conversation, conversation_id)

    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if update.title is not None:
        conversation.title = update.title
    if update.status is not None:
        conversation.status = update.status

    await db.commit()
    await db.refresh(conversation)

    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """대화 삭제 (soft delete)"""
    conversation = await db.get(Conversation, conversation_id)

    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    conversation.status = "deleted"
    await db.commit()


# ─────────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────────


@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessages)
async def list_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    size: int = 50,
):
    """대화의 메시지 목록 조회"""
    # 대화 권한 확인
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    offset = (page - 1) * size

    # 총 개수
    count_query = select(func.count()).select_from(Message).where(
        Message.conversation_id == conversation_id
    )
    total = (await db.execute(count_query)).scalar() or 0

    # 메시지 목록
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(query)
    messages = result.scalars().all()

    items = [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            tokens_used=m.tokens_used,
            model=m.model,
            latency_ms=m.latency_ms,
            created_at=m.created_at,
        )
        for m in messages
    ]

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedMessages(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
