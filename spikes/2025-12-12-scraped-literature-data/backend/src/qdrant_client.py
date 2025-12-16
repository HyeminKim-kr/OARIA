"""
OARIA Literature - Qdrant 클라이언트 (Admin 확장 버전)

Qdrant 벡터 데이터베이스와 상호작용하는 클라이언트입니다.

주요 기능:
- 컬렉션 생성/관리
- 벡터 업서트 (upsert)
- 의미 검색 (semantic search)

역할:
- Qdrant Vector DB 단일 진입점 (SINGLE SOURCE OF TRUTH)
- ETL / RAG / Admin Viewer 공용

설계 이유:
- Qdrant는 고성능 벡터 검색에 최적화
- 768차원 PubMedBERT 임베딩 지원
- 필터링과 페이로드 저장 지원

추가된 Admin 기능:
- 전체 벡터 Scroll 조회
- 단일 벡터 상세 조회
- 컬렉션 초기화 (RESET)
"""

from typing import Optional, Any, List, Tuple
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from .config import settings


class OariaQdrantClient:
    """
    Qdrant 벡터 DB 클라이언트
    
    PubMedBERT 임베딩을 저장하고 검색합니다.

    주요 기능:
    - PubMedBERT (768 dim) 임베딩 저장
    - Semantic Search
    - Admin / Viewer 지원
    """
    
    def __init__(self, url: str = None, collection: str = None):
        self.url = url or settings.qdrant_url
        self.collection = collection or settings.qdrant_collection
        self.vector_size = settings.embedding_dimension
        
        self._client: Optional[QdrantClient] = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
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
    
    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------
    def upsert(
        self,
        pmid: str,
        embedding: list[float],
        payload: dict = None,
    ):
        """벡터 업서트 (삽입 또는 업데이트)"""
        self.ensure_collection()
        client = self._get_client()
        
        payload = payload or {}
        payload["pmid"] = pmid
        
        # 업서트
        client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=int(pmid),
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
            payload = item.get("payload", {})
            payload["pmid"] = item["pmid"]
            
            points.append(
                models.PointStruct(
                    id=int(item["pmid"]),
                    vector=item["embedding"],
                    payload=payload,
                )
            )
        
        if points:
            client.upsert(
                collection_name=self.collection,
                points=points,
            )
    
    # ------------------------------------------------------------------
    # Semantic Search (RAG)
    # ------------------------------------------------------------------
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
            ).points
        except AttributeError:
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
    
    # ------------------------------------------------------------------
    # Admin / Viewer 기능
    # ------------------------------------------------------------------
    def scroll(
        self,
        limit: int = 10,
        offset: Optional[Any] = None,
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> Tuple[List[dict], Optional[Any]]:
        """
        전체 벡터 DB Scroll 조회 (Admin Viewer 용)
        """
        self.ensure_collection()
        client = self._get_client()

        points, next_offset = client.scroll(
            collection_name=self.collection,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vector,
        )

        return (
            [
                {
                    "id": str(p.id),
                    "payload": p.payload,
                    "vector": p.vector if with_vector else None,
                }
                for p in points
            ],
            next_offset,
        )

    # ------------------------------------------------------------------
    # Viewer 기능
    # ------------------------------------------------------------------
    def get_vector(self, pmid: str) -> Optional[dict]:
        """
        단일 벡터 상세 조회 (Expand View)
        """
        self.ensure_collection()
        client = self._get_client()

        result = client.retrieve(
            collection_name=self.collection,
            ids=[int(pmid)],
            with_payload=True,
            with_vectors=True,
        )

        if not result:
            return None

        p = result[0]
        return {
            "id": str(p.id),
            "vector": p.vector,
            "payload": p.payload,
        }

    def get_collection_info(self) -> dict:
        """
        컬렉션 메타 정보
        """
        self.ensure_collection()
        client = self._get_client()

        info = client.get_collection(self.collection)
        return {
            "count": info.points_count,
            "dimension": info.config.params.vectors.size,
            "status": info.status,
        }
    
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
    
    def exists(self, pmid: str) -> bool:
        """특정 PMID가 Qdrant에 존재하는지 확인"""
        self.ensure_collection()
        client = self._get_client()
        
        try:
            point_id = int(pmid)
            result = client.retrieve(
                collection_name=self.collection,
                ids=[point_id],
            )
            return len(result) > 0
        except Exception:
            return False
    
    def get_all_pmids(self, limit: int = 10000) -> list[str]:
        """저장된 모든 PMID 목록 반환"""
        self.ensure_collection()
        client = self._get_client()
        
        try:
            # Scroll을 사용해 모든 포인트 ID 가져오기
            pmids = []
            offset = None
            
            while True:
                results, offset = client.scroll(
                    collection_name=self.collection,
                    limit=1000,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False,
                )
                
                pmids.extend([str(p.id) for p in results])
                
                if offset is None or len(pmids) >= limit:
                    break
            
            return pmids[:limit]
        except Exception as e:
            print(f"⚠️ Failed to get all PMIDs: {e}")
            return []
    
    # ------------------------------------------------------------------
    # ⚠️ DANGER ZONE
    # ------------------------------------------------------------------
    def reset_collection(self):
        """
        ⚠️ 컬렉션 완전 초기화 (Admin Only)
        """
        client = self._get_client()

        print(f"⚠️ RESET collection '{self.collection}'")
        client.delete_collection(self.collection)

        self._initialized = False
        self.ensure_collection()

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------
    def export_to_json(self, filepath: str) -> int:
        """모든 벡터를 JSON 파일로 내보내기"""
        self.ensure_collection()
        client = self._get_client()
        
        try:
            all_points = []
            offset = None
            
            while True:
                results, offset = client.scroll(
                    collection_name=self.collection,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )
                
                for p in points:
                    all_points.append({
                        "id": p.id,
                        "vector": p.vector,
                        "payload": p.payload,
                    })

                if offset is None:
                    break

            
            with open(filepath, 'w') as f:
                import json
                json.dump(
                    {
                        "collection": self.collection,
                        "vector_size": self.vector_size,
                        "exported_at": datetime.now().isoformat(),
                        "points": all_points,
                    },
                    f,
                    indent=2,
                )
            
            print(f"✅ Exported {len(all_points)} vectors to {filepath}")
            return len(all_points)
        except Exception as e:
            print(f"❌ Export failed: {e}")
            raise
    
    def import_from_json(self, filepath: str) -> int:
        """JSON 파일에서 벡터 가져오기"""
        import json
        self.ensure_collection()
        client = self._get_client()
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            points = data.get("points", [])
            if not points:
                return 0
            
            # 배치로 업서트
            batch_size = 100
            imported = 0
            
            for i in range(0, len(points), batch_size):
                batch = points[i:i+batch_size]
                qdrant_points = [
                    models.PointStruct(
                        id=p["id"],
                        vector=p["vector"],
                        payload=p.get("payload", {}),
                    )
                    for p in batch
                ]
                
                client.upsert(
                    collection_name=self.collection,
                    points=qdrant_points,
                )
                imported += len(batch)
            
            print(f"✅ Imported {imported} vectors from {filepath}")
            return imported
        except Exception as e:
            print(f"❌ Import failed: {e}")
            raise


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------
_qdrant_instance: Optional[OariaQdrantClient] = None


def get_qdrant_client() -> OariaQdrantClient:
    """싱글톤 Qdrant 클라이언트 반환"""
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = OariaQdrantClient()
    return _qdrant_instance

