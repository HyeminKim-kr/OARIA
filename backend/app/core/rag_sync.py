"""RAG 전략 동기화

서버 시작 시 코드에 정의된 전략 정보를 DB에 동기화합니다.

흐름:
1. Backend 전략: registry에서 추출 (retrievers, rerankers)
2. Batch 전략: batch_strategies.py에서 추출 (chunkers, embedders)
3. DB에 UPSERT
4. 코드에 없는 전략은 is_active=false
"""

import logging
from typing import List, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RAGStrategy
from app.rag import registry
from app.rag.batch_strategies import get_all_batch_strategies

logger = logging.getLogger(__name__)


async def sync_rag_strategies(session: AsyncSession) -> Dict[str, int]:
    """RAG 전략을 DB에 동기화

    Args:
        session: AsyncSession

    Returns:
        동기화 결과 {"inserted": n, "updated": n, "deactivated": n}
    """
    logger.info("Starting RAG strategies sync...")

    # 1. 코드에서 전략 정보 수집
    strategies_from_code = _collect_all_strategies()
    logger.info(f"Collected {len(strategies_from_code)} strategies from code")

    # 2. DB에 UPSERT
    inserted = 0
    updated = 0

    for strategy in strategies_from_code:
        stmt = insert(RAGStrategy).values(
            category=strategy["category"],
            name=strategy["name"],
            description=strategy["description"],
            config=strategy["config"],
            location=strategy["location"],
            is_active=True,
        )

        # ON CONFLICT DO UPDATE
        stmt = stmt.on_conflict_do_update(
            constraint="uq_rag_strategies_category_name",
            set_={
                "description": stmt.excluded.description,
                "config": stmt.excluded.config,
                "location": stmt.excluded.location,
                "is_active": True,
            },
        )

        result = await session.execute(stmt)
        if result.rowcount > 0:
            inserted += 1

    # 3. 코드에 없는 전략 비활성화
    code_names = {(s["category"], s["name"]) for s in strategies_from_code}

    # 현재 활성화된 전략 조회
    stmt = select(RAGStrategy).where(RAGStrategy.is_active == True)
    result = await session.execute(stmt)
    active_strategies = result.scalars().all()

    deactivated = 0
    for strategy in active_strategies:
        if (strategy.category, strategy.name) not in code_names:
            strategy.is_active = False
            deactivated += 1
            logger.info(f"Deactivated strategy: {strategy.category}/{strategy.name}")

    await session.commit()

    result = {
        "inserted": inserted,
        "updated": updated,
        "deactivated": deactivated,
        "total": len(strategies_from_code),
    }
    logger.info(f"RAG strategies sync completed: {result}")

    return result


def _collect_all_strategies() -> List[Dict[str, Any]]:
    """코드에서 모든 전략 정보 수집"""
    strategies = []

    # 1. Backend 전략 (retrievers, rerankers)
    backend_categories = ["retriever", "reranker"]

    for category in backend_categories:
        info_func = getattr(registry, f"get_{category}_info", None)
        if info_func:
            for info in info_func():
                strategies.append({
                    "category": category,
                    "name": info["name"],
                    "description": info.get("description", ""),
                    "config": info.get("config", {}),
                    "location": "backend",
                })

    # 2. Batch 전략 (chunkers, embedders)
    batch_strategies = get_all_batch_strategies()

    for category, items in batch_strategies.items():
        for item in items:
            strategies.append({
                "category": category,
                "name": item["name"],
                "description": item.get("description", ""),
                "config": item.get("config", {}),
                "location": "batch",
            })

    return strategies
