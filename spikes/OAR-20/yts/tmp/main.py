# -*- coding: utf-8 -*-
"""
OAR-20: 암 논문 데이터 수집 스파이크 - CLI 진입점

이 모듈은 다양한 데이터 소스에서 암 관련 논문을 수집하는 CLI 도구입니다.

사용법:
    # 메타데이터만 수집 (빠름)
    uv run python main.py collect --source europe_pmc --query "lung cancer" --limit 10

    # 전문(Full-text) 포함 수집 (느림, Europe PMC Open Access만)
    uv run python main.py collect-fulltext --query "breast cancer" --limit 5

    # 데이터 소스 정보 확인
    uv run python main.py info

작성자: yts
작성일: 2025-12-19
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.collectors.europe_pmc import EuropePMCCollector

# ============================================================
# CLI 앱 설정
# ============================================================

app = typer.Typer(help="암 논문 수집 CLI (Cancer Paper Collection CLI)")
console = Console()

# 샘플 데이터 저장 경로
SAMPLES_DIR = Path(__file__).parent / "samples"


# ============================================================
# 명령어 1: collect - 메타데이터 수집
# ============================================================

@app.command()
def collect(
    query: str = typer.Option("neoplasms", "--query", "-q", help="검색 쿼리"),
    limit: int = typer.Option(10, "--limit", "-l", help="최대 결과 수"),
    save: bool = typer.Option(True, "--save/--no-save", help="파일 저장 여부"),
):
    """
    Europe PMC에서 논문 메타데이터를 수집합니다 (초록만, 전문 미포함).

    전문이 필요하면 collect-fulltext 명령을 사용하세요.

    Examples:
        # 종양학 논문 10건 수집
        uv run python main.py collect -q "neoplasms" -l 10

        # 폐암 논문 20건 수집
        uv run python main.py collect -q "lung cancer" -l 20
    """

    console.print(f"\n[bold blue]EUROPE PMC에서 수집 중...[/bold blue]")
    console.print(f"   쿼리: {query}, 최대: {limit}건")

    # Europe PMC collector로 검색
    collector = EuropePMCCollector()
    papers = collector.search(query=query, limit=limit)

    # 결과 테이블 출력
    table = Table(title=f"Europe PMC 결과 ({len(papers)}건)")
    table.add_column("PMCID", style="cyan", no_wrap=True)
    table.add_column("제목", style="white", max_width=60)
    table.add_column("연도", style="green")

    for paper in papers:
        table.add_row(
            paper.get("pmcid", "N/A"),
            paper.get("title", "N/A")[:60],
            str(paper.get("year", "N/A")),
        )

    console.print(table)

    # JSON 파일로 저장
    if save and papers:
        save_path = SAMPLES_DIR / "europe_pmc" / f"{query.replace(' ', '_')}_{limit}.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)

        console.print(f"[green]저장됨: {save_path}[/green]")


# ============================================================
# 명령어 2: collect-fulltext - 전문 포함 수집
# ============================================================

@app.command("collect-fulltext")
def collect_fulltext(
    query: str = typer.Option("neoplasms", "--query", "-q", help="검색 쿼리"),
    limit: int = typer.Option(10, "--limit", "-l", help="최대 결과 수"),
    save: bool = typer.Option(True, "--save/--no-save", help="파일 저장 여부"),
):
    """
    Europe PMC에서 Open Access 논문의 전문(Full-text)을 수집합니다.

    주의:
    - Open Access 논문만 전문 수집 가능 (자동으로 OA 필터 적용)
    - 전문 수집은 논문당 약 0.5초 소요 (API 부하 방지)
    - 수집된 전문은 섹션별로 파싱됨 (Abstract, Methods, Results 등)

    Examples:
        # 암 관련 OA 논문 10건 + 전문 수집
        uv run python main.py collect-fulltext -q "cancer" -l 10

        # 유방암 OA 논문 5건 + 전문 수집
        uv run python main.py collect-fulltext -q "breast cancer" -l 5
    """

    # 헤더 출력
    console.print(f"\n[bold magenta]== 전문 수집 (Europe PMC) ==[/bold magenta]")
    console.print(f"   쿼리: {query} AND OPEN_ACCESS:Y")
    console.print(f"   최대: {limit}건\n")

    # Europe PMC collector 생성 (API 호출 간 0.5초 딜레이)
    collector = EuropePMCCollector(delay=0.5)

    # 프로그레스 표시와 함께 수집 실행
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Open Access 논문 검색 및 전문 수집 중...", total=None)
        papers = collector.search_with_fulltext(query=query, limit=limit)

    # 결과 테이블 출력
    table = Table(title=f"Europe PMC 전문 수집 결과 ({len(papers)}건)")
    table.add_column("#", style="dim", width=3)
    table.add_column("PMCID", style="cyan", width=12)
    table.add_column("제목", style="white", max_width=50)
    table.add_column("연도", style="green", width=6)
    table.add_column("전문", style="yellow", width=10)

    for i, paper in enumerate(papers, 1):
        # 전문 수집 여부 표시
        has_fulltext = "Yes" if paper.get("full_text") else "No"
        fulltext_style = "green" if has_fulltext == "Yes" else "red"
        table.add_row(
            str(i),
            paper.get("pmcid", "N/A"),
            (paper.get("title", "N/A") or "N/A")[:50],
            str(paper.get("year", "N/A")),
            f"[{fulltext_style}]{has_fulltext}[/{fulltext_style}]",
        )

    console.print(table)

    # 통계 출력
    fulltext_count = sum(1 for p in papers if p.get("full_text"))
    console.print(f"\n[bold]요약:[/bold]")
    console.print(f"   전체 논문: {len(papers)}건")
    console.print(f"   전문 수집: {fulltext_count}건")

    # JSON 파일로 저장
    if save and papers:
        save_path = SAMPLES_DIR / "europe_pmc" / f"fulltext_{query.replace(' ', '_')}_{limit}.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)

        console.print(f"\n[green]저장됨: {save_path}[/green]")


# ============================================================
# 명령어 3: info - 데이터 소스 정보
# ============================================================

@app.command()
def info():
    """
    수집 전략 및 데이터 소스 정보를 표시합니다.
    """

    console.print("\n[bold]== OAR-20: 암 논문 수집 스파이크 ==[/bold]\n")

    console.print("[cyan]타겟:[/cyan] 종양학(Oncology) 연구자")
    console.print("[cyan]소스:[/cyan] Europe PMC (단일)")
    console.print("[cyan]쿼리:[/cyan] neoplasms AND OPEN_ACCESS:Y")
    console.print("[cyan]전문:[/cyan] Open Access 논문만 수집 가능\n")

    table = Table(title="Europe PMC 데이터")
    table.add_column("구분", style="cyan")
    table.add_column("수량", style="green")

    table.add_row("암 논문 전체", "~530만건")
    table.add_row("Open Access", "~200만건 (38%)")
    table.add_row("전문 수집 가능", "~200만건")

    console.print(table)

    console.print("\n[bold]명령어:[/bold]")
    console.print("  collect          메타데이터 + 초록 수집")
    console.print("  collect-fulltext 메타데이터 + 초록 + 전문 수집")


# ============================================================
# 메인 실행
# ============================================================

if __name__ == "__main__":
    app()
