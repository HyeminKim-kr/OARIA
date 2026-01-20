"""
OAR-19 파싱 파이프라인 데모

실행:
    cd spikes/OAR-19/yts
    uv run streamlit run demo_app.py
"""

import streamlit as st
import asyncio
from datetime import datetime

from src.pipeline import Pipeline, PipelineStep, AsyncPipeline, BatchResult
from src.europe_pmc_client import PaperInfo, EuropePMCClient
from src.models import ParsedPaper
from src.config import Config
from src.storage import DatabaseStorage, S3Storage


# 페이지 설정
st.set_page_config(
    page_title="OAR-19 파싱 파이프라인",
    page_icon="📄",
    layout="wide",
)

# 세션 상태 초기화
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "processed_papers" not in st.session_state:
    st.session_state.processed_papers = []  # 처리된 논문 히스토리
if "selected_paper_detail" not in st.session_state:
    st.session_state.selected_paper_detail = None
if "selected_error_detail" not in st.session_state:
    st.session_state.selected_error_detail = None  # 실패한 논문 에러 상세
if "processing" not in st.session_state:
    st.session_state.processing = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "수집"  # 수집 or 조회
if "stored_papers" not in st.session_state:
    st.session_state.stored_papers = []
if "selected_stored_paper" not in st.session_state:
    st.session_state.selected_stored_paper = None


def format_duration(ms: int) -> str:
    """밀리초를 읽기 쉬운 형태로 변환"""
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms/1000:.1f}s"


def format_size(size_bytes: int) -> str:
    """바이트를 읽기 쉬운 형태로 변환"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


async def load_stored_papers():
    """DB에서 저장된 논문 목록 로드"""
    config = Config.from_env()
    db = DatabaseStorage(config)

    async with db.connect():
        papers = await db.get_papers(limit=100)
        count = await db.get_papers_count()
        return papers, count


async def load_paper_details(paper_id: str):
    """DB에서 논문 상세 정보 로드"""
    config = Config.from_env()
    db = DatabaseStorage(config)

    async with db.connect():
        return await db.get_paper_with_details(paper_id)


async def search_stored_papers(keyword: str):
    """DB에서 논문 검색"""
    config = Config.from_env()
    db = DatabaseStorage(config)

    async with db.connect():
        return await db.search_papers(keyword, limit=50)


def load_s3_text(canonical_prefix: str, version: str = "v1"):
    """S3에서 canonical text 로드"""
    config = Config.from_env()
    s3 = S3Storage(config)
    return s3.get_canonical_text(canonical_prefix, version)


def load_s3_metadata(canonical_prefix: str):
    """S3에서 versions.json 로드"""
    config = Config.from_env()
    s3 = S3Storage(config)
    return s3.get_versions_metadata(canonical_prefix)


def load_s3_files(canonical_prefix: str):
    """S3에서 파일 목록 로드"""
    config = Config.from_env()
    s3 = S3Storage(config)
    return s3.list_paper_files(canonical_prefix)


def render_view_page():
    """수집된 논문 조회 페이지"""
    st.title("📚 수집된 논문 조회")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.header("🗄️ 저장된 논문 목록")

        # 검색
        search_keyword = st.text_input("🔍 검색 (제목/초록)", placeholder="키워드 입력...")

        # 로드 버튼
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 목록 새로고침", use_container_width=True):
                with st.spinner("DB에서 논문 목록 로딩 중..."):
                    try:
                        papers, count = asyncio.run(load_stored_papers())
                        st.session_state.stored_papers = papers
                        st.success(f"총 {count}개 논문 중 {len(papers)}개 로드됨")
                    except Exception as e:
                        st.error(f"DB 연결 실패: {e}")
        with col2:
            if search_keyword and st.button("🔍 검색", use_container_width=True):
                with st.spinner("검색 중..."):
                    try:
                        papers = asyncio.run(search_stored_papers(search_keyword))
                        st.session_state.stored_papers = papers
                        st.info(f"{len(papers)}개 검색됨")
                    except Exception as e:
                        st.error(f"검색 실패: {e}")

        st.divider()

        # 논문 목록 표시
        if st.session_state.stored_papers:
            for i, paper in enumerate(st.session_state.stored_papers):
                paper_id = paper.get("paper_id", "N/A")
                title = paper.get("title", "제목 없음")
                year = paper.get("year", "N/A")
                source = paper.get("source", "N/A")

                with st.container():
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        st.markdown(f"**{title[:60]}{'...' if len(title) > 60 else ''}**")
                        st.caption(f"📅 {year} | 🆔 {paper_id} | 📡 {source}")
                    with col_b:
                        if st.button("보기", key=f"view_{i}", use_container_width=True):
                            st.session_state.selected_stored_paper = paper
                            st.rerun()

                st.divider()
        else:
            st.info("📥 '목록 새로고침' 버튼을 클릭하여 DB에서 논문을 로드하세요")

    with col_right:
        st.header("📑 논문 상세 정보")

        if st.session_state.selected_stored_paper:
            paper = st.session_state.selected_stored_paper
            paper_id = paper.get("paper_id")

            st.subheader(paper.get("title", "제목 없음")[:80])

            # 기본 메타데이터
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("연도", paper.get("year", "N/A"))
            with col2:
                st.metric("길이", f"{paper.get('canonical_text_length', 0):,}")
            with col3:
                st.metric("버전", paper.get("canonical_text_version", "v1"))

            # 탭
            tab1, tab2, tab3, tab4 = st.tabs(["DB 정보", "저자/섹션", "S3 텍스트", "S3 메타데이터"])

            with tab1:
                # DB에서 가져온 정보
                st.json({
                    "paper_id": paper.get("paper_id"),
                    "pmcid": paper.get("pmcid"),
                    "pmid": paper.get("pmid"),
                    "doi": paper.get("doi"),
                    "journal": paper.get("journal"),
                    "source": paper.get("source"),
                    "source_url": paper.get("source_url"),
                    "canonical_prefix": paper.get("canonical_prefix"),
                    "canonical_text_hash": paper.get("canonical_text_hash", "")[:16] + "..." if paper.get("canonical_text_hash") else None,
                    "created_at": str(paper.get("created_at")),
                    "updated_at": str(paper.get("updated_at")),
                })

                # 원본 논문 링크
                source_url = paper.get("source_url")
                if source_url:
                    st.markdown(f"🔗 [원본 논문 보기]({source_url})")

            with tab2:
                # 저자 및 섹션 정보 로드
                if st.button("📥 저자/섹션 로드", key="load_details"):
                    with st.spinner("상세 정보 로딩 중..."):
                        try:
                            details = asyncio.run(load_paper_details(paper_id))
                            if details:
                                # 저자
                                st.markdown("### 👥 저자")
                                for author in details.get("authors", []):
                                    corresp = " ⭐" if author.get("is_corresponding") else ""
                                    orcid = f" ({author.get('orcid')})" if author.get("orcid") else ""
                                    st.markdown(f"**{author.get('author_order')}. {author.get('author_name')}**{corresp}{orcid}")
                                    if author.get("affiliation"):
                                        st.caption(f"└ {author.get('affiliation')[:100]}...")

                                # 섹션
                                st.markdown("### 📑 섹션")
                                for section in details.get("sections", []):
                                    offset_info = f"offset: {section.get('offset_start')} ~ {section.get('offset_end')}"
                                    st.markdown(f"**[{section.get('section_order')}] {section.get('section_name').upper()}**: {section.get('section_title', '')[:40]}")
                                    st.caption(offset_info)
                            else:
                                st.warning("상세 정보를 찾을 수 없습니다")
                        except Exception as e:
                            st.error(f"로드 실패: {e}")

            with tab3:
                # S3에서 canonical text 로드
                canonical_prefix = paper.get("canonical_prefix")
                if canonical_prefix:
                    if st.button("📥 S3 텍스트 로드", key="load_s3_text"):
                        with st.spinner("S3에서 텍스트 로딩 중..."):
                            try:
                                text = load_s3_text(canonical_prefix)
                                if text:
                                    st.text_area(
                                        f"Canonical Text (총 {len(text):,}자)",
                                        text[:5000] + ("..." if len(text) > 5000 else ""),
                                        height=400,
                                        disabled=True,
                                    )
                                else:
                                    st.warning("S3에서 텍스트를 찾을 수 없습니다")
                            except Exception as e:
                                st.error(f"S3 로드 실패: {e}")
                else:
                    st.warning("canonical_prefix가 없습니다")

            with tab4:
                # S3 메타데이터 및 파일 목록
                canonical_prefix = paper.get("canonical_prefix")
                if canonical_prefix:
                    if st.button("📥 S3 메타데이터 로드", key="load_s3_meta"):
                        with st.spinner("S3에서 메타데이터 로딩 중..."):
                            try:
                                # versions.json
                                metadata = load_s3_metadata(canonical_prefix)
                                if metadata:
                                    st.markdown("### versions.json")
                                    st.json(metadata)

                                # 파일 목록
                                files = load_s3_files(canonical_prefix)
                                if files:
                                    st.markdown("### 📁 S3 파일 목록")
                                    for f in files:
                                        st.markdown(f"- `{f['key']}` ({format_size(f['size'])})")
                                        st.caption(f"  수정: {f['last_modified']}")
                                else:
                                    st.info("S3에 파일이 없습니다")
                            except Exception as e:
                                st.error(f"S3 로드 실패: {e}")
                else:
                    st.warning("canonical_prefix가 없습니다")

            # 닫기 버튼
            if st.button("❌ 닫기"):
                st.session_state.selected_stored_paper = None
                st.rerun()
        else:
            st.info("👈 왼쪽에서 논문을 선택하세요")

            # 통계 표시
            if st.session_state.stored_papers:
                st.subheader("📊 저장 현황")
                st.metric("저장된 논문", len(st.session_state.stored_papers))

                # 연도별 분포
                years = [p.get("year") for p in st.session_state.stored_papers if p.get("year")]
                if years:
                    year_counts = {}
                    for y in years:
                        year_counts[y] = year_counts.get(y, 0) + 1
                    st.bar_chart(year_counts)


def render_collect_page():
    """논문 수집 및 처리 페이지"""
    st.title("📄 OAR-19 파싱 파이프라인 데모")

    # 사이드바 내용은 main에서 관리
    with st.sidebar:
        st.header("⚙️ 설정")
        save_to_db = st.checkbox("PostgreSQL 저장", value=True)
        save_to_s3 = st.checkbox("S3 저장 (MinIO)", value=False)

        st.divider()

        # 히스토리
        st.header("📋 처리 히스토리")
        if st.session_state.processed_papers:
            st.caption(f"총 {len(st.session_state.processed_papers)}개 처리됨")

            for i, item in enumerate(reversed(st.session_state.processed_papers)):
                status_icon = "✅" if item["success"] else "❌"
                with st.expander(f"{status_icon} {item['pmcid']}", expanded=False):
                    st.write(f"**{item['title'][:50]}...**")
                    st.caption(f"저자: {item['authors']}명 | 섹션: {item['sections']}개")
                    st.caption(f"처리: {item['duration']}")

                    # 실패 시 에러 메시지 표시
                    if not item["success"]:
                        # 실패한 단계 찾기
                        failed_step = None
                        for step in item.get("steps", []):
                            if step.status == "error":
                                failed_step = step
                                break

                        if failed_step:
                            st.error(f"❌ **{failed_step.name}** 단계 실패")
                            st.code(failed_step.message, language=None)
                        elif item.get("error"):
                            st.error(item["error"][:200])

                        if st.button("에러 상세", key=f"error_{i}"):
                            st.session_state.selected_error_detail = item
                            st.session_state.selected_paper_detail = None
                    else:
                        if st.button("상세 보기", key=f"detail_{i}"):
                            st.session_state.selected_paper_detail = item.get("paper")
                            st.session_state.selected_error_detail = None

            if st.button("🗑️ 히스토리 초기화"):
                st.session_state.processed_papers = []
                st.session_state.selected_paper_detail = None
                st.session_state.selected_error_detail = None
                st.rerun()
        else:
            st.info("처리된 논문이 없습니다")

    # 메인 영역
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.header("🔍 논문 검색 및 처리")

        # 검색 입력
        query = st.text_input(
            "검색어",
            value="lung cancer immunotherapy",
            placeholder="예: breast cancer, EGFR mutation",
        )

        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            limit = st.number_input("검색 수", min_value=1, max_value=10000, value=5, step=10)
        with col2:
            max_concurrent = st.number_input("동시 처리", min_value=1, value=5, step=5, help="병렬 처리 수 (높을수록 빠르지만 API 제한 주의)")
        with col3:
            search_btn = st.button("🔍 검색", type="secondary", use_container_width=True)
        with col4:
            process_btn = st.button("🚀 검색 & 처리", type="primary", use_container_width=True)

        # 검색만 하는 경우
        if search_btn:
            with st.spinner("Europe PMC에서 검색 중..."):
                pipeline = Pipeline()
                try:
                    results = pipeline.run_search(query, limit=limit)
                    st.session_state.search_results = results
                    st.success(f"{len(results)}개 논문 검색됨")
                except Exception as e:
                    st.error(f"검색 실패: {e}")
                finally:
                    pipeline.close()

        # 검색 후 자동 처리 (병렬)
        if process_btn:
            st.session_state.processing = True

            try:
                # 검색
                with st.spinner("Europe PMC에서 검색 중..."):
                    client = EuropePMCClient()
                    results = client.search(query, limit=limit, open_access_only=True)
                    client.close()
                    st.session_state.search_results = results

                if not results:
                    st.warning("검색 결과가 없습니다")
                else:
                    st.info(f"🚀 {len(results)}개 논문 **병렬** 처리 중...")

                    # 진행률 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    completed_count = 0
                    total_count = len([r for r in results if r.pmcid])

                    def on_progress(done, total, msg):
                        nonlocal completed_count
                        completed_count = done
                        progress_bar.progress(done / total if total > 0 else 0)
                        status_text.text(f"{msg} ({done}/{total})")

                    # 병렬 처리 실행
                    start_time = datetime.now()

                    async def run_parallel():
                        pipeline = AsyncPipeline(
                            max_concurrent=max_concurrent,
                            on_progress=on_progress,
                        )
                        return await pipeline.run_batch(
                            query=query,
                            paper_infos=results,
                            save_to_db=save_to_db,
                            save_to_s3=save_to_s3,
                        )

                    batch_result: BatchResult = asyncio.run(run_parallel())
                    total_duration = datetime.now() - start_time

                    status_text.empty()
                    progress_bar.empty()

                    # 결과를 히스토리에 추가
                    paper_info_map = {p.pmcid: p for p in results if p.pmcid}
                    for r in batch_result.results:
                        paper_info = paper_info_map.get(r.pmcid)
                        st.session_state.processed_papers.append({
                            "pmcid": r.pmcid,
                            "pmid": paper_info.pmid if paper_info else None,
                            "title": paper_info.title if paper_info else r.pmcid,
                            "success": r.success,
                            "error": r.error,
                            "authors": len(r.paper.authors) if r.paper else 0,
                            "sections": len(r.paper.sections) if r.paper else 0,
                            "duration": format_duration(sum(s.duration_ms or 0 for s in r.steps)),
                            "paper": r.paper,
                            "steps": r.steps,
                        })

                    # 결과 요약
                    st.success(
                        f"✅ 완료: {batch_result.success}/{batch_result.total}개 성공 "
                        f"({batch_result.duration_sec:.1f}초, 병렬 처리)"
                    )

                    # 순차 대비 속도 비교 표시
                    estimated_sequential = batch_result.total * 5  # 논문당 약 5초 가정
                    if batch_result.duration_sec > 0:
                        speedup = estimated_sequential / batch_result.duration_sec
                        if speedup > 1.5:
                            st.info(f"⚡ 순차 처리 대비 약 **{speedup:.1f}배** 빠름 (예상 {estimated_sequential}초 → 실제 {batch_result.duration_sec:.1f}초)")

            except Exception as e:
                st.error(f"오류 발생: {e}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                st.session_state.processing = False

        # 검색 결과 표시
        if st.session_state.search_results:
            st.subheader("검색 결과")
            for i, paper in enumerate(st.session_state.search_results):
                # 이미 처리되었는지 확인
                is_processed = any(
                    p["pmcid"] == paper.pmcid
                    for p in st.session_state.processed_papers
                )
                status = "✅" if is_processed else "⏳"

                st.markdown(f"{status} **{paper.title[:60]}{'...' if len(paper.title) > 60 else ''}**")
                st.caption(f"📰 {paper.journal or 'N/A'} | 📅 {paper.year or 'N/A'} | PMC: {paper.pmcid or 'N/A'} | PMID: {paper.pmid or 'N/A'}")

    with col_right:
        st.header("📑 상세 정보")

        # 에러 상세 정보 표시
        if st.session_state.selected_error_detail:
            item = st.session_state.selected_error_detail

            st.subheader(f"❌ {item['pmcid']} 에러 상세")
            st.markdown(f"**{item['title'][:80]}{'...' if len(item['title']) > 80 else ''}**")

            # 메타데이터
            col1, col2 = st.columns(2)
            with col1:
                st.caption(f"PMID: {item.get('pmid', 'N/A')}")
            with col2:
                st.caption(f"처리 시간: {item['duration']}")

            st.divider()

            # 파이프라인 단계별 상태
            st.markdown("### 📊 파이프라인 단계")

            steps = item.get("steps", [])
            if steps:
                for step in steps:
                    if step.status == "success":
                        st.success(f"✅ **{step.name}**: {step.message}")
                        if step.duration_ms:
                            st.caption(f"   ⏱️ {format_duration(step.duration_ms)}")
                    elif step.status == "error":
                        st.error(f"❌ **{step.name}**: 실패")
                        st.markdown("**에러 메시지:**")
                        st.code(step.message, language=None)
                        if step.duration_ms:
                            st.caption(f"   ⏱️ {format_duration(step.duration_ms)}")

                        # 추가 데이터가 있으면 표시
                        if step.data:
                            with st.expander("🔍 디버그 데이터"):
                                st.json(step.data)
                    elif step.status == "pending":
                        st.info(f"⏳ **{step.name}**: 대기 중")
                    else:
                        st.warning(f"🔄 **{step.name}**: {step.status}")
            else:
                # steps가 없는 경우 (예외로 인한 실패)
                st.error("파이프라인 단계 정보 없음")

            # 전체 에러 메시지
            if item.get("error"):
                st.markdown("### 💥 전체 에러")
                st.code(item["error"], language=None)

            # 닫기 버튼
            if st.button("닫기"):
                st.session_state.selected_error_detail = None
                st.rerun()

        elif st.session_state.selected_paper_detail:
            paper: ParsedPaper = st.session_state.selected_paper_detail

            # 기본 정보
            st.subheader(paper.title[:80] + "..." if len(paper.title) > 80 else paper.title)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("저자", len(paper.authors))
            with col2:
                st.metric("섹션", len(paper.sections))
            with col3:
                st.metric("길이", f"{paper.canonical_text_length:,}")

            # 탭으로 상세 정보
            tab1, tab2, tab3, tab4 = st.tabs(["메타데이터", "저자", "섹션", "Canonical Text"])

            with tab1:
                st.json({
                    "paper_id": paper.paper_id,
                    "pmcid": paper.pmcid,
                    "pmid": paper.pmid,
                    "doi": paper.doi,
                    "year": paper.year,
                    "journal": paper.journal,
                    "keywords": paper.keywords[:5] if paper.keywords else [],
                    "hash": paper.canonical_text_hash[:16] + "...",
                })

            with tab2:
                for author in paper.authors:
                    corresp = " ⭐" if author.is_corresponding else ""
                    orcid = f" ({author.orcid})" if author.orcid else ""
                    st.markdown(f"**{author.order}. {author.name}**{corresp}{orcid}")
                    if author.affiliation:
                        st.caption(f"└ {author.affiliation[:100]}...")

            with tab3:
                for section in paper.sections:
                    with st.expander(f"[{section.order}] {section.name.upper()}: {section.title[:40]}..."):
                        st.caption(f"Offset: {section.offset_start} ~ {section.offset_end} ({section.char_count:,} chars)")
                        st.text_area(
                            "내용",
                            section.text[:1500] + ("..." if len(section.text) > 1500 else ""),
                            height=120,
                            key=f"sec_{section.order}",
                            disabled=True,
                        )

            with tab4:
                st.text_area(
                    "Canonical Text (처음 3000자)",
                    paper.canonical_text[:3000] + "..." if len(paper.canonical_text) > 3000 else paper.canonical_text,
                    height=300,
                    disabled=True,
                )

            # 청킹 연계 데이터
            with st.expander("OAR-18 청킹 모듈 연계 데이터 (JSON)"):
                st.json(paper.to_chunking_dict())

        else:
            st.info("👈 왼쪽 사이드바에서 논문을 선택하세요")

            # 최근 처리 결과 요약
            if st.session_state.processed_papers:
                st.subheader("📊 처리 현황")

                total = len(st.session_state.processed_papers)
                success = sum(1 for p in st.session_state.processed_papers if p["success"])

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("전체", total)
                with col2:
                    st.metric("성공", success)
                with col3:
                    st.metric("실패", total - success)

                # 최근 5개 결과
                st.markdown("**최근 처리 결과:**")
                for item in st.session_state.processed_papers[-5:]:
                    status = "✅" if item["success"] else "❌"
                    st.text(f"{status} {item['pmcid']} - {item['title'][:40]}...")

                    # 실패 시 간단한 에러 정보 표시
                    if not item["success"]:
                        # 실패한 단계 찾기
                        failed_step_name = None
                        failed_message = None
                        for step in item.get("steps", []):
                            if step.status == "error":
                                failed_step_name = step.name
                                failed_message = step.message[:100]
                                break

                        if failed_step_name:
                            st.caption(f"   └ {failed_step_name}: {failed_message}...")
                        elif item.get("error"):
                            st.caption(f"   └ {item['error'][:100]}...")


def main():
    """메인 함수 - 페이지 라우팅"""
    # 사이드바 상단: 페이지 선택
    with st.sidebar:
        st.header("📌 페이지 선택")
        page = st.radio(
            "페이지",
            ["🔬 수집", "📚 조회"],
            index=0 if st.session_state.current_page == "수집" else 1,
            label_visibility="collapsed",
        )

        if page == "🔬 수집" and st.session_state.current_page != "수집":
            st.session_state.current_page = "수집"
            st.rerun()
        elif page == "📚 조회" and st.session_state.current_page != "조회":
            st.session_state.current_page = "조회"
            st.rerun()

        st.divider()

    # 페이지 렌더링
    if st.session_state.current_page == "수집":
        render_collect_page()
    else:
        render_view_page()


if __name__ == "__main__":
    main()
