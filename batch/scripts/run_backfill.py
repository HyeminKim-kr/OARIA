#!/usr/bin/env python
"""Backfill 직접 실행 스크립트 (테스트용)

Celery 없이 직접 backfill 실행

Usage:
    # 첫 번째 활성 쿼리로 실행
    python scripts/run_backfill.py

    # 특정 쿼리 ID로 실행
    python scripts/run_backfill.py <query_id>

    # 쿼리 목록 조회
    python scripts/run_backfill.py --list
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from src.config import settings
from src.tasks.backfill import run_backfill_async


def list_queries():
    """활성화된 검색 쿼리 목록"""
    conn = psycopg.connect(settings.db.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, query, priority, total_collected, last_backfill_at
                FROM search_queries
                WHERE is_active = true
                ORDER BY priority
                """
            )
            rows = cur.fetchall()

            print("\n=== 활성화된 검색 쿼리 ===\n")
            for row in rows:
                print(f"ID: {row[0]}")
                print(f"  이름: {row[1]}")
                print(f"  쿼리: {row[2]}")
                print(f"  우선순위: {row[3]}")
                print(f"  수집 건수: {row[4]}")
                print(f"  마지막 실행: {row[5]}")
                print()

    finally:
        conn.close()


def get_first_query_id() -> str | None:
    """첫 번째 활성 쿼리 ID"""
    conn = psycopg.connect(settings.db.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM search_queries
                WHERE is_active = true
                ORDER BY priority
                LIMIT 1
                """
            )
            row = cur.fetchone()
            return str(row[0]) if row else None
    finally:
        conn.close()


async def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_queries()
            return

        query_id = sys.argv[1]
    else:
        query_id = get_first_query_id()
        if not query_id:
            print("활성화된 검색 쿼리가 없습니다.")
            print("--list 옵션으로 쿼리 목록을 확인하세요.")
            return

    print(f"\n=== Backfill 시작: {query_id} ===\n")

    result = await run_backfill_async(query_id)

    print(f"\n=== Backfill 완료 ===")
    print(f"  Job ID: {result['job_id']}")
    print(f"  처리: {result['processed']}")
    print(f"  성공: {result['success']}")
    print(f"  실패: {result['failed']}")


if __name__ == "__main__":
    asyncio.run(main())
