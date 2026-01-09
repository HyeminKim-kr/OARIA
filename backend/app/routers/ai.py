"""AI 라우터

Ask AI 엔드포인트 (SSE 스트리밍 with Agent Task Decomposition)
대화 CRUD 엔드포인트
"""

import asyncio
import json
import queue
import threading
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

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
    Reference,
)
from app.services import agent_service


router = APIRouter(prefix="/ai", tags=["ai"])


# ─────────────────────────────────────────────────────────────
# Ask AI (SSE Streaming with Agent Task Decomposition)
# ─────────────────────────────────────────────────────────────


@router.post("/ask")
async def ask_ai(
    request: AskRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """AI에게 질문하기 (SSE 스트리밍, Agent 기반 태스크 분해)

    복잡한 질문을 자동으로 분석하여:
    - Simple: 기존 RAG 파이프라인 사용
    - Medium/Complex: 태스크 분해 후 병렬/순차 실행

    Returns:
        SSE 스트림:
        - event: status (진행 상태)
        - event: complexity (복잡도 분석 결과)
        - event: subtasks (분해된 태스크 목록)
        - event: task_start (태스크 실행 시작)
        - event: task_complete (태스크 완료)
        - event: token (LLM 응답 토큰)
        - event: references (검색된 참조 문헌)
        - event: done (완료, conversation_id 포함)
    """
    # 대화 조회 (기존 대화인 경우만 미리 검증)
    conversation = None
    if request.conversation_id:
        conversation = await db.get(Conversation, request.conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    async def generate_sse():
        """SSE 스트림 생성 (Agent 실행)"""
        nonlocal conversation
        total_start = time.perf_counter()

        # 이벤트 큐 (Agent 서비스에서 이벤트를 푸시)
        event_queue: queue.Queue = queue.Queue()

        def run_agent():
            """별도 스레드에서 Agent 실행"""
            try:
                # Agent 스트림 실행
                result_gen = agent_service.execute_stream(
                    query=request.question,
                    conversation_id=str(request.conversation_id) if request.conversation_id else None,
                )

                # 이벤트를 큐에 푸시하고 return value를 캡처
                # Generator의 return 값은 StopIteration.value로 전달됨
                try:
                    while True:
                        event = next(result_gen)
                        event_queue.put(("event", event))
                except StopIteration as e:
                    # Generator의 return 값 (AgentResult)
                    result = e.value
                    event_queue.put(("result", result))

            except Exception as e:
                import traceback
                traceback.print_exc()
                event_queue.put(("error", str(e)))
            finally:
                event_queue.put(("done", None))

        # 스레드 시작
        agent_thread = threading.Thread(target=run_agent)
        agent_thread.start()

        # 이벤트 처리
        agent_result = None
        while True:
            try:
                item = await asyncio.to_thread(event_queue.get, timeout=60)
            except Exception:
                break

            event_type, data = item

            if event_type == "done":
                break
            elif event_type == "error":
                yield {
                    "event": "error",
                    "data": json.dumps({"error": data}, ensure_ascii=False),
                }
                break
            elif event_type == "result":
                agent_result = data
            elif event_type == "event":
                # AgentEvent를 SSE 이벤트로 변환
                yield {
                    "event": data.event_type,
                    "data": json.dumps(data.data, ensure_ascii=False),
                }

        agent_thread.join()

        if not agent_result:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Agent execution failed"}, ensure_ascii=False),
            }
            return

        # 대화 생성/업데이트
        if not conversation:
            title = request.question[:50] + "..." if len(request.question) > 50 else request.question
            new_conversation = Conversation(
                user_id=current_user.id,
                title=title,
            )
            db.add(new_conversation)
            await db.flush()
            conv = new_conversation
        else:
            conv = conversation

        # 사용자 메시지 저장
        user_message = Message(
            conversation_id=conv.id,
            role="user",
            content=request.question,
        )
        db.add(user_message)
        await db.flush()

        # Assistant 메시지 저장
        total_latency = int((time.perf_counter() - total_start) * 1000)

        assistant_message = Message(
            conversation_id=conv.id,
            role="assistant",
            content=agent_result.answer,
            tokens_used=None,  # Agent doesn't track tokens the same way
            model="agent-gpt-4o-mini",
            latency_ms=total_latency,
        )
        db.add(assistant_message)
        await db.flush()

        # Answer Log 저장 (evidence를 flat list로 저장)
        evidence_data = [ref.model_dump() for ref in agent_result.references]

        answer_log = AnswerLog(
            message_id=assistant_message.id,
            conversation_id=conv.id,
            user_id=current_user.id,
            question=request.question,
            answer=agent_result.answer,
            search_query=request.question,
            search_filters=request.filters.model_dump() if request.filters else None,
            evidence=evidence_data,
            model="agent-gpt-4o-mini",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            search_latency_ms=agent_result.total_duration_ms,
            llm_latency_ms=0,
            total_latency_ms=total_latency,
        )
        db.add(answer_log)
        await db.commit()

        # References 이벤트 전송
        references_data = [ref.model_dump() for ref in agent_result.references]
        yield {
            "event": "references",
            "data": json.dumps({"references": references_data}, ensure_ascii=False),
        }

        # Done 이벤트 전송
        yield {
            "event": "done",
            "data": json.dumps({
                "conversation_id": str(conv.id),
                "message_id": str(assistant_message.id),
            }),
        }

    return EventSourceResponse(generate_sse())


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
    """대화의 메시지 목록 조회 (assistant 메시지에 references 포함)"""
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

    # 메시지 목록 (AnswerLog 조인)
    from sqlalchemy.orm import selectinload

    query = (
        select(Message)
        .options(selectinload(Message.answer_log))
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(query)
    messages = result.scalars().all()

    items = []
    for m in messages:
        # assistant 메시지이고 answer_log가 있으면 evidence를 references로 변환
        references = None
        if m.role == "assistant" and m.answer_log and m.answer_log.evidence:
            references = [
                Reference(
                    paper_id=e.get("paper_id", ""),
                    chunk_id=e.get("chunk_id", ""),
                    title=e.get("title", ""),
                    journal=e.get("journal"),
                    year=e.get("year"),
                    section=e.get("section", ""),
                    snippet=e.get("snippet", ""),
                    offset_start=e.get("offset_start", 0),
                    offset_end=e.get("offset_end", 0),
                    text_version=e.get("text_version", "v1"),
                    distance=e.get("distance", 0.0),
                )
                for e in m.answer_log.evidence
            ]

        items.append(
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                tokens_used=m.tokens_used,
                model=m.model,
                latency_ms=m.latency_ms,
                created_at=m.created_at,
                references=references,
            )
        )

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedMessages(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
