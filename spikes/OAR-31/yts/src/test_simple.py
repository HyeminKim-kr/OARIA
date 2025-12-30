"""간단한 Weaviate 테스트 (샘플 데이터)

스키마 생성 + 샘플 삽입 + 검색 확인
"""

import uuid
from datetime import datetime, timezone

import weaviate
import weaviate.classes as wvc
from weaviate.classes.query import Filter, MetadataQuery

from schema import COLLECTION_NAME, create_paper_chunk_collection
from embeddings import EmbeddingClient


def run_simple_test():
    """간단한 테스트 실행"""
    print("=" * 60)
    print("OAR-31: Weaviate 간단 테스트 (샘플 데이터)")
    print("=" * 60)

    # 1. Weaviate 연결
    print("\n📡 Weaviate 연결...")
    client = weaviate.connect_to_local()

    try:
        # 2. 스키마 생성
        create_paper_chunk_collection(client)

        # 3. 컬렉션 가져오기
        collection = client.collections.get(COLLECTION_NAME)

        # 4. 임베딩 클라이언트
        print("\n🔧 임베딩 클라이언트 초기화...")
        embedding_client = EmbeddingClient()
        print(f"   모드: {'Mock' if embedding_client.use_mock else 'OpenAI'}")
        print(f"   버전: {embedding_client.get_version_string()}")

        # 5. 샘플 데이터 삽입
        print("\n📤 샘플 데이터 삽입...")
        sample_chunks = [
            {
                "paperId": "pmc:PMC00000001",
                "chunkId": "pmc:PMC00000001|abstract|0",
                "pmcid": "PMC00000001",
                "title": "Immunotherapy in Non-Small Cell Lung Cancer",
                "section": "abstract",
                "chunkIndex": 0,
                "content": "Immune checkpoint inhibitors have revolutionized the treatment of non-small cell lung cancer. PD-1 and PD-L1 inhibitors show significant improvement in overall survival.",
                "year": 2024,
            },
            {
                "paperId": "pmc:PMC00000001",
                "chunkId": "pmc:PMC00000001|methods|0",
                "pmcid": "PMC00000001",
                "title": "Immunotherapy in Non-Small Cell Lung Cancer",
                "section": "methods",
                "chunkIndex": 0,
                "content": "We conducted a retrospective analysis of 500 patients treated with pembrolizumab or nivolumab between 2018 and 2023.",
                "year": 2024,
            },
            {
                "paperId": "pmc:PMC00000002",
                "chunkId": "pmc:PMC00000002|abstract|0",
                "pmcid": "PMC00000002",
                "title": "CAR-T Cell Therapy for Solid Tumors",
                "section": "abstract",
                "chunkIndex": 0,
                "content": "Chimeric antigen receptor T-cell therapy has shown promise in hematological malignancies. However, solid tumors remain challenging due to immunosuppressive microenvironment.",
                "year": 2023,
            },
        ]

        inserted = 0
        for chunk in sample_chunks:
            # 이미 존재하는지 확인
            existing = collection.query.fetch_objects(
                filters=Filter.by_property("chunkId").equal(chunk["chunkId"]),
                limit=1,
            )
            if existing.objects:
                print(f"   ⏭️ 이미 존재: {chunk['chunkId']}")
                continue

            # 임베딩 생성
            embedding = embedding_client.embed_text(chunk["content"])

            # 삽입
            object_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunkId"]))
            collection.data.insert(
                uuid=object_uuid,
                properties={
                    **chunk,
                    "embeddingVersion": embedding_client.get_version_string(),
                    "offsetStart": 0,
                    "offsetEnd": len(chunk["content"]),
                    "textVersion": "sample_v1",
                    "createdAt": datetime.now(timezone.utc),
                },
                vector=embedding,
            )
            print(f"   ✅ 삽입: {chunk['chunkId']}")
            inserted += 1

        # 6. 통계
        count = collection.aggregate.over_all(total_count=True).total_count
        print(f"\n📊 저장된 청크: {count}개 (새로 삽입: {inserted}개)")

        # 7. 검색 테스트
        print("\n" + "=" * 60)
        print("🔍 검색 테스트")
        print("=" * 60)

        test_query = "lung cancer immunotherapy"
        query_vector = embedding_client.embed_text(test_query)

        # 벡터 검색
        print(f"\n1️⃣ 벡터 검색: '{test_query}'")
        results = collection.query.near_vector(
            near_vector=query_vector,
            limit=3,
            return_metadata=MetadataQuery(distance=True),
        )
        for i, obj in enumerate(results.objects):
            print(f"   [{i+1}] {obj.properties['title'][:40]}...")
            print(f"       섹션: {obj.properties['section']}, 거리: {obj.metadata.distance:.4f}")

        # 필터 + 벡터 검색
        print(f"\n2️⃣ 필터 + 벡터 검색: year >= 2024")
        results = collection.query.near_vector(
            near_vector=query_vector,
            filters=Filter.by_property("year").greater_or_equal(2024),
            limit=3,
            return_metadata=MetadataQuery(distance=True),
        )
        for i, obj in enumerate(results.objects):
            print(f"   [{i+1}] {obj.properties['title'][:40]}... (year: {obj.properties['year']})")

        # 하이브리드 검색
        print(f"\n3️⃣ 하이브리드 검색: 'CAR-T solid tumor'")
        results = collection.query.hybrid(
            query="CAR-T solid tumor",
            vector=embedding_client.embed_text("CAR-T solid tumor"),
            alpha=0.5,
            limit=3,
            return_metadata=MetadataQuery(score=True),
        )
        for i, obj in enumerate(results.objects):
            print(f"   [{i+1}] {obj.properties['title'][:40]}...")
            print(f"       점수: {obj.metadata.score:.4f}")

        print("\n✅ 모든 테스트 통과!")

    finally:
        client.close()


if __name__ == "__main__":
    run_simple_test()
