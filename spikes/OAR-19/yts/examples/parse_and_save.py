"""
파싱 및 저장 예제

사용법:
    python -m examples.parse_and_save <xml_file>
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.parser import parse_fulltext_xml
from src.storage import DatabaseStorage, S3Storage


async def main(xml_path: str):
    """XML 파일 파싱 후 DB/S3 저장"""

    # 설정 로드
    config = Config.from_env()
    print(f"DB: {config.db.dsn}")
    print(f"S3: {config.s3.endpoint_url}/{config.s3.bucket}")

    # XML 읽기
    xml_content = Path(xml_path).read_text(encoding="utf-8")
    print(f"\nXML 파일: {xml_path}")
    print(f"크기: {len(xml_content):,} bytes")

    # 파싱
    print("\n--- 파싱 시작 ---")
    paper = parse_fulltext_xml(xml_content)

    print(f"Paper ID: {paper.paper_id}")
    print(f"제목: {paper.title}")
    print(f"연도: {paper.year}")
    print(f"저널: {paper.journal}")
    print(f"저자 수: {len(paper.authors)}")
    print(f"섹션 수: {len(paper.sections)}")
    print(f"canonical_text 길이: {paper.canonical_text_length:,} chars")
    print(f"해시: {paper.canonical_text_hash[:16]}...")

    # 저자 정보 출력
    print("\n--- 저자 ---")
    for author in paper.authors:
        corresp = " (교신)" if author.is_corresponding else ""
        orcid = f" [{author.orcid}]" if author.orcid else ""
        print(f"  {author.order}. {author.name}{corresp}{orcid}")

    # 섹션 정보 출력
    print("\n--- 섹션 ---")
    for section in paper.sections:
        print(f"  {section.order}. {section.name}: offset {section.offset_start}-{section.offset_end} ({section.char_count} chars)")

    # S3 저장
    print("\n--- S3 저장 ---")
    s3_storage = S3Storage(config)
    s3_result = s3_storage.save_all(paper)
    print(f"text: {s3_result['text_key']}")
    print(f"metadata: {s3_result['metadata_key']}")

    # DB 저장
    print("\n--- DB 저장 ---")
    db_storage = DatabaseStorage(config)
    async with db_storage.connect():
        db_result = await db_storage.save_all(paper)
        print(f"paper_id: {db_result['paper_id']}")
        print(f"저자 저장: {db_result['authors_count']}명")
        print(f"섹션 저장: {db_result['sections_count']}개")

    print("\n완료!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python -m examples.parse_and_save <xml_file>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
