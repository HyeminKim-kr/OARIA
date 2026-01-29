"""Research Assistant 라우터

Vector Graph 엔드포인트 - 연구 질문 기반 벡터 그래프 생성
"""

import asyncio
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models import Paper, PaperAuthor
from app.services.embedding_service import embedding_service
from app.services.weaviate_service import weaviate_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/research", tags=["research"])


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────


class VectorSearchRequest(BaseModel):
    """벡터 그래프 검색 요청"""
    query: str = Field(..., min_length=2, description="검색 쿼리")
    limit: int = Field(default=30, ge=5, le=100, description="최대 논문 수")
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0, description="최소 유사도")
    include_authors: bool = Field(default=True, description="저자 노드 포함 여부")
    include_keywords: bool = Field(default=True, description="키워드 노드 포함 여부")


class NodeMetadata(BaseModel):
    """노드 메타데이터"""
    pmid: Optional[str] = None
    journal: Optional[str] = None
    pubdate: Optional[str] = None
    abstract: Optional[str] = None
    paper_count: Optional[int] = None
    certainty_score: Optional[float] = None
    domain: Optional[str] = None


class GraphNode(BaseModel):
    """그래프 노드"""
    id: str
    type: str  # paper, author, keyword, concept
    label: str
    cluster: Optional[str] = None
    metadata: Optional[NodeMetadata] = None


class GraphLink(BaseModel):
    """그래프 링크"""
    source: str
    target: str
    type: str  # similar, authored, contains
    similarity: Optional[float] = None
    weight: Optional[float] = None
    evidence_hint: Optional[str] = None


class VectorGraphResponse(BaseModel):
    """벡터 그래프 응답"""
    nodes: list[GraphNode]
    links: list[GraphLink]
    query: str
    total_papers: int
    total_authors: int
    total_keywords: int


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.post("/vector-graph", response_model=VectorGraphResponse)
async def search_vector_graph(
    request: VectorSearchRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """벡터 기반 연구 그래프 검색

    연구 질문을 벡터화하여 유사한 논문들을 검색하고,
    논문-저자-키워드 관계를 그래프로 반환합니다.
    """
    logger.info(f"Vector graph search: query={request.query[:50]}... user={current_user.id}")

    try:
        # 1. 쿼리 임베딩 (OpenAI 실패시 mock 사용)
        use_mock = False
        try:
            query_vector = await embedding_service.embed_text(request.query)
        except Exception as embed_error:
            logger.warning(f"Embedding failed, using hybrid search with low alpha: {embed_error}")
            # Mock 임베딩 사용 + 하이브리드 검색에서 키워드 비중 높임
            query_vector = embedding_service._mock_embed(request.query)
            use_mock = True

        # 2. Weaviate에서 하이브리드 검색 (키워드 + 벡터)
        # alpha: 0=키워드만, 1=벡터만, 0.5=균형
        # 임베딩 실패시 키워드 비중을 높임 (alpha=0.2)
        alpha = 0.2 if use_mock else 0.7

        search_results = await asyncio.to_thread(
            weaviate_service.search_hybrid,
            query=request.query,
            query_vector=query_vector,
            limit=request.limit * 3,  # 중복 제거 여유분
            alpha=alpha,
        )

        logger.info(f"Hybrid search results: {len(search_results)} chunks found (alpha={alpha})")

        if not search_results:
            return VectorGraphResponse(
                nodes=[],
                links=[],
                query=request.query,
                total_papers=0,
                total_authors=0,
                total_keywords=0,
            )

        # 3. 논문별로 그룹화 (가장 높은 유사도 사용)
        paper_scores: dict[str, dict] = {}
        for chunk in search_results:
            paper_id = chunk.get("paperId", "")
            if not paper_id:
                continue

            # 하이브리드 검색은 score 반환, 벡터 검색은 distance 반환
            if "score" in chunk:
                similarity = min(chunk.get("score", 0), 1.0)  # score는 0~1+ 범위
            else:
                distance = chunk.get("distance", 1.0)
                similarity = 1.0 - distance

            # 하이브리드 검색에서는 min_similarity 조건 완화
            min_sim = request.min_similarity * 0.5 if use_mock else request.min_similarity
            if similarity < min_sim:
                continue

            if paper_id not in paper_scores or similarity > paper_scores[paper_id]["similarity"]:
                paper_scores[paper_id] = {
                    "paper_id": paper_id,
                    "similarity": similarity,
                    "title": chunk.get("title", "Unknown"),
                    "journal": chunk.get("journal"),
                    "year": chunk.get("year"),
                    "section": chunk.get("section", ""),
                    "text_snippet": chunk.get("content", "")[:200],
                }

        # 상위 N개 논문만 선택
        sorted_papers = sorted(
            paper_scores.values(),
            key=lambda x: x["similarity"],
            reverse=True
        )[:request.limit]

        logger.info(f"Papers after grouping: {len(paper_scores)} -> {len(sorted_papers)} (after limit)")

        paper_ids = [p["paper_id"] for p in sorted_papers]

        # 4. DB에서 논문 상세 정보 조회
        db_papers = {}
        if paper_ids:
            query = select(Paper).where(Paper.paper_id.in_(paper_ids))
            result = await db.execute(query)
            for paper in result.scalars():
                db_papers[paper.paper_id] = paper

        # 5. 저자 정보 조회
        authors_by_paper: dict[str, list[str]] = {}
        if request.include_authors and paper_ids:
            author_query = (
                select(PaperAuthor)
                .where(PaperAuthor.paper_id.in_([p.id for p in db_papers.values() if p]))
            )
            author_result = await db.execute(author_query)
            for author in author_result.scalars():
                paper = next((p for p in db_papers.values() if p.id == author.paper_id), None)
                if paper:
                    if paper.paper_id not in authors_by_paper:
                        authors_by_paper[paper.paper_id] = []
                    authors_by_paper[paper.paper_id].append(author.author_name)

        # 6. 그래프 노드 생성
        nodes: list[GraphNode] = []
        links: list[GraphLink] = []

        author_nodes: dict[str, str] = {}  # author_name -> node_id
        keyword_nodes: dict[str, str] = {}  # keyword -> node_id

        # 논문 노드 생성
        for paper_data in sorted_papers:
            paper_id = paper_data["paper_id"]
            db_paper = db_papers.get(paper_id)

            node_id = f"p_{paper_id.replace(':', '_')}"

            # 클러스터 결정 (유사도 기반)
            similarity = paper_data["similarity"]
            if similarity >= 0.85:
                cluster = "high_relevance"
            elif similarity >= 0.75:
                cluster = "medium_relevance"
            else:
                cluster = "low_relevance"

            metadata = NodeMetadata(
                pmid=db_paper.pmid if db_paper else None,
                journal=paper_data.get("journal") or (db_paper.journal if db_paper else None),
                pubdate=str(paper_data.get("year") or (db_paper.year if db_paper else "")),
                abstract=paper_data.get("text_snippet"),
                certainty_score=similarity,
            )

            nodes.append(GraphNode(
                id=node_id,
                type="paper",
                label=paper_data.get("title") or (db_paper.title if db_paper else "Unknown"),
                cluster=cluster,
                metadata=metadata,
            ))

            # 저자 노드 및 링크 생성
            if request.include_authors:
                paper_authors = authors_by_paper.get(paper_id, [])
                for author_name in paper_authors[:5]:  # 최대 5명
                    if author_name not in author_nodes:
                        author_id = f"a_{len(author_nodes)}"
                        author_nodes[author_name] = author_id
                        nodes.append(GraphNode(
                            id=author_id,
                            type="author",
                            label=author_name,
                            metadata=NodeMetadata(paper_count=1),
                        ))
                    else:
                        # 논문 수 업데이트
                        for n in nodes:
                            if n.id == author_nodes[author_name] and n.metadata:
                                n.metadata.paper_count = (n.metadata.paper_count or 0) + 1

                    links.append(GraphLink(
                        source=author_nodes[author_name],
                        target=node_id,
                        type="authored",
                        similarity=1.0,
                    ))

            # 키워드 노드 및 링크 생성
            if request.include_keywords and db_paper and db_paper.keywords:
                for keyword in db_paper.keywords[:5]:  # 최대 5개
                    keyword_lower = keyword.lower()
                    if keyword_lower not in keyword_nodes:
                        keyword_id = f"k_{len(keyword_nodes)}"
                        keyword_nodes[keyword_lower] = keyword_id
                        nodes.append(GraphNode(
                            id=keyword_id,
                            type="keyword",
                            label=keyword,
                        ))

                    links.append(GraphLink(
                        source=node_id,
                        target=keyword_nodes[keyword_lower],
                        type="contains",
                        similarity=1.0,
                    ))

        # 7. 논문 간 유사도 링크 생성
        paper_node_ids = [f"p_{p['paper_id'].replace(':', '_')}" for p in sorted_papers]
        for i, paper1 in enumerate(sorted_papers):
            for j, paper2 in enumerate(sorted_papers[i+1:], i+1):
                # 두 논문의 유사도 추정 (쿼리와의 유사도 기반)
                sim1 = paper1["similarity"]
                sim2 = paper2["similarity"]
                # 같은 클러스터에 있을수록 유사
                estimated_similarity = min(sim1, sim2) * 0.9

                if estimated_similarity >= request.min_similarity:
                    links.append(GraphLink(
                        source=paper_node_ids[i],
                        target=paper_node_ids[j],
                        type="similar",
                        similarity=round(estimated_similarity, 3),
                    ))

        logger.info(
            f"Vector graph result: papers={len(sorted_papers)} "
            f"authors={len(author_nodes)} keywords={len(keyword_nodes)} "
            f"links={len(links)}"
        )

        return VectorGraphResponse(
            nodes=nodes,
            links=links,
            query=request.query,
            total_papers=len(sorted_papers),
            total_authors=len(author_nodes),
            total_keywords=len(keyword_nodes),
        )

    except Exception as e:
        logger.error(f"Vector graph search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {str(e)}",
        )


@router.post("/decompose")
async def decompose_query(
    query: str,
    current_user: CurrentUser,
):
    """연구 질문을 시맨틱 개념으로 분해 (향후 구현)"""
    # TODO: LLM을 사용하여 질문을 개념 노드로 분해
    return {
        "core_question": query,
        "concept_nodes": [],
        "relation_edges": [],
    }
