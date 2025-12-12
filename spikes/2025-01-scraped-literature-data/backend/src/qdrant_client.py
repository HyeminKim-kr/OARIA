"""
OARIA Literature - Qdrant 클라이언트

Qdrant 벡터 데이터베이스와 상호작용하는 클라이언트입니다.

주요 기능:
- 컬렉션 생성/관리
- 벡터 업서트 (upsert)
- 의미 검색 (semantic search)

설계 이유:
- Qdrant는 고성능 벡터 검색에 최적화
- 768차원 PubMedBERT 임베딩 지원
- 필터링과 페이로드 저장 지원
"""

from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from .config import settings


class OariaQdrantClient:
    """
    Qdrant 벡터 DB 클라이언트
    
    PubMedBERT 임베딩을 저장하고 검색합니다.
    """
    
    def __init__(self, url: str = None, collection: str = None):
        self.url = url or settings.qdrant_url
        self.collection = collection or settings.qdrant_collection
        self.vector_size = settings.embedding_dimension
        
        self._client: Optional[QdrantClient] = None
        self._initialized = False
    
    def _get_client(self) -> QdrantClient:
        """Qdrant 클라이언트 반환"""
        if self._client is None:
            try:
                self._client = QdrantClient(url=self.url)
                print(f"🔌 Connected to Qdrant at {self.url}")
            except Exception as e:
                print(f"⚠️  Qdrant connection failed: {e}")
                raise
        return self._client
    
    def ensure_collection(self):
        """컬렉션이 존재하는지 확인하고 없으면 생성"""
        if self._initialized:
            return
        
        client = self._get_client()
        
        try:
            # 컬렉션 존재 여부 확인
            client.get_collection(self.collection)
            print(f"✅ Collection '{self.collection}' exists")
        except (UnexpectedResponse, Exception):
            # 컬렉션 생성
            client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            print(f"✅ Collection '{self.collection}' created")
        
        self._initialized = True
    
    def upsert(
        self,
        pmid: str,
        embedding: list[float],
        payload: dict = None,
    ):
        """벡터 업서트 (삽입 또는 업데이트)"""
        self.ensure_collection()
        client = self._get_client()
        
        # PMID를 정수 ID로 변환 (Qdrant는 숫자 ID 권장)
        point_id = int(pmid)
        
        # 페이로드 준비
        if payload is None:
            payload = {}
        payload["pmid"] = pmid
        
        # 업서트
        client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
    
    def upsert_batch(
        self,
        items: list[dict],
    ):
        """
        배치 업서트
        
        items: [{"pmid": "123", "embedding": [...], "payload": {...}}, ...]
        """
        self.ensure_collection()
        client = self._get_client()
        
        points = []
        for item in items:
            pmid = item["pmid"]
            point_id = int(pmid)
            
            payload = item.get("payload", {})
            payload["pmid"] = pmid
            
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=item["embedding"],
                    payload=payload,
                )
            )
        
        if points:
            client.upsert(
                collection_name=self.collection,
                points=points,
            )
    
    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        score_threshold: float = 0.5,
    ) -> list[dict]:
        """
        의미 검색
        
        Returns:
            [{"pmid": "123", "score": 0.95, "payload": {...}}, ...]
        """
        self.ensure_collection()
        client = self._get_client()
        
        # qdrant-client >= 1.7에서는 query_points 사용
        try:
            results = client.query_points(
                collection_name=self.collection,
                query=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
            )
            
            return [
                {
                    "pmid": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results.points
            ]
        except AttributeError:
            # 구 버전 qdrant-client 호환
            results = client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
            )
            
            return [
                {
                    "pmid": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results
            ]
    
    def get_count(self) -> int:
        """컬렉션의 포인트 수 반환"""
        self.ensure_collection()
        client = self._get_client()
        
        info = client.get_collection(self.collection)
        return info.points_count
    
    def delete(self, pmid: str):
        """포인트 삭제"""
        self.ensure_collection()
        client = self._get_client()
        
        point_id = int(pmid)
        client.delete(
            collection_name=self.collection,
            points_selector=models.PointIdsList(points=[point_id]),
        )


# 싱글톤 인스턴스
_qdrant_instance: Optional[OariaQdrantClient] = None


def get_qdrant_client() -> OariaQdrantClient:
    """싱글톤 Qdrant 클라이언트 반환"""
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = OariaQdrantClient()
    return _qdrant_instance
