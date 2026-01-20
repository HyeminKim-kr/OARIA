"""Citation 검증 스크립트

RAG 답변에서 인용된 내용이 실제 논문에 있는지 확인
"""

import sys
from pathlib import Path

import weaviate
from weaviate.classes.query import Filter

# OAR-31 Weaviate 임포트
OAR_31_PATH = Path(__file__).parent.parent.parent.parent / "OAR-31" / "yts" / "src"
sys.path.insert(0, str(OAR_31_PATH))
from schema import COLLECTION_NAME


def verify_paper_content(pmcid: str, keyword: str):
    """특정 논문에서 키워드 포함 청크 검색"""
    client = weaviate.connect_to_local()
    try:
        collection = client.collections.get(COLLECTION_NAME)

        # 해당 논문의 모든 청크 조회
        results = collection.query.fetch_objects(
            filters=Filter.by_property("pmcid").equal(pmcid),
            limit=100,
        )

        print(f"\n📄 {pmcid} 논문에서 '{keyword}' 검색")
        print("=" * 60)

        found = []
        for obj in results.objects:
            content = obj.properties.get("content", "")
            if keyword.lower() in content.lower():
                found.append({
                    "section": obj.properties.get("section"),
                    "chunk_index": obj.properties.get("chunkIndex"),
                    "content": content,
                })

        if found:
            print(f"✅ {len(found)}개 청크에서 발견됨:\n")
            for i, item in enumerate(found[:3]):  # 최대 3개만 표시
                print(f"[{i+1}] 섹션: {item['section']} (청크 #{item['chunk_index']})")
                # 키워드 주변 컨텍스트 표시
                content = item['content']
                idx = content.lower().find(keyword.lower())
                start = max(0, idx - 50)
                end = min(len(content), idx + len(keyword) + 100)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                print(f"    \"{snippet}\"")
                print()
        else:
            print(f"❌ '{keyword}'를 찾을 수 없음")

    finally:
        client.close()


def list_paper_sections(pmcid: str):
    """논문의 섹션 구조 확인"""
    client = weaviate.connect_to_local()
    try:
        collection = client.collections.get(COLLECTION_NAME)

        results = collection.query.fetch_objects(
            filters=Filter.by_property("pmcid").equal(pmcid),
            limit=100,
        )

        print(f"\n📋 {pmcid} 논문 섹션 구조")
        print("=" * 60)

        sections = {}
        for obj in results.objects:
            section = obj.properties.get("section", "unknown")
            if section not in sections:
                sections[section] = 0
            sections[section] += 1

        for section, count in sorted(sections.items()):
            print(f"  - {section}: {count}개 청크")

        print(f"\n총 {sum(sections.values())}개 청크")

    finally:
        client.close()


def run_verification():
    """주요 Citation 검증 실행"""
    print("=" * 60)
    print("OAR-11: Citation 검증")
    print("=" * 60)

    # 테스트 케이스들
    verifications = [
        # (PMCID, 검색할 키워드, 설명)
        ("PMC12625643", "PD-1", "폐암 면역치료 PD-1 언급"),
        ("PMC12625643", "M7824", "M7824 bifunctional protein"),
        ("PMC12625643", "SX-682", "CXCR2 antagonist SX-682"),
        ("PMC12583504", "KRAS", "KRAS mutation"),
        ("PMC12570465", "neuro-immune", "neuro-immune axis"),
        ("PMC12541881", "CCR8", "CCR8 monoclonal antibody"),
        ("PMC12541881", "BAY 3375968", "BAY 3375968 clinical trial"),
    ]

    for pmcid, keyword, desc in verifications:
        print(f"\n\n{'─' * 60}")
        print(f"검증: {desc}")
        verify_paper_content(pmcid, keyword)

    # 논문별 섹션 구조
    print("\n\n" + "=" * 60)
    print("논문별 섹션 구조")
    print("=" * 60)

    for pmcid in ["PMC12625643", "PMC12583504", "PMC12570465"]:
        list_paper_sections(pmcid)


if __name__ == "__main__":
    run_verification()
