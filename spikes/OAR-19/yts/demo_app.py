"""
OAR-19 파싱 파이프라인 데모

실행:
    cd spikes/OAR-19/yts
    uv run streamlit run demo_app.py
"""

import streamlit as st
import asyncio
from datetime import datetime

from src.pipeline import Pipeline, PipelineStep
from src.europe_pmc_client import PaperInfo
from src.models import ParsedPaper


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


def format_duration(ms: int) -> str:
    """밀리초를 읽기 쉬운 형태로 변환"""
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms/1000:.1f}s"


def main():
    st.title("📄 OAR-19 파싱 파이프라인 데모")

    # 사이드바: 설정 및 히스토리
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

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            limit = st.slider("검색 수", min_value=1, max_value=20, value=5)
        with col2:
            search_btn = st.button("🔍 검색", type="secondary", use_container_width=True)
        with col3:
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

        # 검색 후 자동 처리
        if process_btn:
            st.session_state.processing = True

            # 검색
            pipeline = Pipeline()
            try:
                with st.spinner("Europe PMC에서 검색 중..."):
                    results = pipeline.run_search(query, limit=limit)
                    st.session_state.search_results = results

                if not results:
                    st.warning("검색 결과가 없습니다")
                else:
                    st.info(f"📊 {len(results)}개 논문 파이프라인 처리 중...")

                    # 진행률 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    # 각 논문 처리
                    for idx, paper_info in enumerate(results):
                        if not paper_info.pmcid:
                            continue

                        status_text.text(f"처리 중: {paper_info.pmcid} ({idx+1}/{len(results)})")
                        start_time = datetime.now()

                        try:
                            if save_to_db:
                                result = asyncio.run(pipeline.run_single_async(
                                    query=query,
                                    pmcid=paper_info.pmcid,
                                    save_to_db=True,
                                    save_to_s3=save_to_s3,
                                    paper_info=paper_info,
                                ))
                            else:
                                result = pipeline.run_single(
                                    query=query,
                                    pmcid=paper_info.pmcid,
                                    save_to_s3=save_to_s3,
                                    save_to_db=False,
                                    paper_info=paper_info,
                                )

                            duration = datetime.now() - start_time

                            # 히스토리에 추가
                            st.session_state.processed_papers.append({
                                "pmcid": paper_info.pmcid,
                                "pmid": paper_info.pmid,
                                "title": paper_info.title,
                                "success": result.success,
                                "error": result.error,
                                "authors": len(result.paper.authors) if result.paper else 0,
                                "sections": len(result.paper.sections) if result.paper else 0,
                                "duration": format_duration(int(duration.total_seconds() * 1000)),
                                "paper": result.paper,
                                "steps": result.steps,
                            })

                        except Exception as e:
                            st.session_state.processed_papers.append({
                                "pmcid": paper_info.pmcid,
                                "pmid": paper_info.pmid,
                                "title": paper_info.title,
                                "success": False,
                                "error": str(e),
                                "authors": 0,
                                "sections": 0,
                                "duration": "N/A",
                                "paper": None,
                                "steps": [],
                            })

                        progress_bar.progress((idx + 1) / len(results))

                    status_text.empty()
                    progress_bar.empty()

                    # 결과 요약
                    success_count = sum(1 for p in st.session_state.processed_papers[-len(results):] if p["success"])
                    st.success(f"✅ 완료: {success_count}/{len(results)}개 성공")

            except Exception as e:
                st.error(f"오류 발생: {e}")
            finally:
                pipeline.close()
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


if __name__ == "__main__":
    main()
