"""
OAR-9: 논문 수집 파이프라인 데모

Streamlit 기반 UI
- 논문 검색 및 수집
- PostgreSQL + S3 저장
- 저장된 논문 조회
"""

import asyncio
import streamlit as st
from datetime import datetime

from src.config import Config
from src.europe_pmc_client import AsyncEuropePMCClient
from src.parser import PaperParser
from src.storage import DatabaseStorage, S3Storage
from src.pipeline import Pipeline


# 페이지 설정
st.set_page_config(
    page_title="OAR-9: 논문 수집 파이프라인",
    page_icon="📚",
    layout="wide",
)

st.title("📚 OAR-9: 논문 수집 파이프라인")
st.caption("Europe PMC → PostgreSQL + S3")

# 사이드바: 설정
with st.sidebar:
    st.header("⚙️ 설정")

    st.subheader("데이터베이스")
    db_host = st.text_input("Host", value="localhost")
    db_port = st.number_input("Port", value=5432, min_value=1, max_value=65535)
    db_user = st.text_input("User", value="oaria")
    db_password = st.text_input("Password", value="oaria123", type="password")
    db_name = st.text_input("Database", value="oaria")

    st.subheader("S3/MinIO")
    s3_endpoint = st.text_input("Endpoint", value="http://localhost:9000")
    s3_access_key = st.text_input("Access Key", value="minioadmin")
    s3_secret_key = st.text_input("Secret Key", value="minioadmin", type="password")
    s3_bucket = st.text_input("Bucket", value="oaria-papers")

    st.subheader("API 설정")
    max_concurrent = st.slider("동시 요청 수", min_value=1, max_value=50, value=10)
    api_delay = st.slider("요청 간격 (초)", min_value=0.0, max_value=1.0, value=0.1, step=0.05)


def get_config() -> Config:
    """현재 설정으로 Config 생성"""
    from src.config import DatabaseConfig, S3Config, APIConfig

    return Config(
        db=DatabaseConfig(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
        ),
        s3=S3Config(
            endpoint_url=s3_endpoint,
            access_key=s3_access_key,
            secret_key=s3_secret_key,
            bucket=s3_bucket,
        ),
        api=APIConfig(
            max_concurrent=max_concurrent,
            delay=api_delay,
        ),
    )


# 탭 구성
tab1, tab2, tab3 = st.tabs(["🔍 검색 & 수집", "📋 저장된 논문", "📄 논문 상세"])


# ========== 탭 1: 검색 & 수집 ==========
with tab1:
    st.header("논문 검색 및 수집")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "검색 쿼리",
            value="lung cancer",
            placeholder="예: lung cancer, breast cancer treatment",
        )
    with col2:
        limit = st.number_input("검색 수", min_value=1, max_value=1000, value=10)

    col3, col4, col5 = st.columns(3)
    with col3:
        save_to_db = st.checkbox("PostgreSQL 저장", value=True)
    with col4:
        save_to_s3 = st.checkbox("S3 저장", value=True)
    with col5:
        search_only = st.checkbox("검색만 (수집 안함)", value=False)

    if st.button("🚀 실행", type="primary", use_container_width=True):
        config = get_config()

        if search_only:
            # 검색만
            st.subheader("검색 결과")

            async def search_papers():
                async with AsyncEuropePMCClient(
                    max_concurrent=config.api.max_concurrent,
                    delay=config.api.delay,
                ) as client:
                    return await client.search(query, limit=limit, open_access_only=True)

            with st.spinner("검색 중..."):
                papers = asyncio.run(search_papers())

            if papers:
                st.success(f"✅ {len(papers)}개 논문 검색 완료")

                for i, paper in enumerate(papers, 1):
                    with st.expander(f"{i}. {paper.title[:80]}...", expanded=i <= 3):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**PMID:** {paper.pmid or 'N/A'}")
                        with col2:
                            st.write(f"**PMCID:** {paper.pmcid or 'N/A'}")
                        with col3:
                            st.write(f"**Year:** {paper.year or 'N/A'}")

                        st.write(f"**Journal:** {paper.journal or 'N/A'}")
                        st.write(f"**Open Access:** {'✅' if paper.is_open_access else '❌'}")
                        st.write(f"**Full Text:** {'✅' if paper.has_full_text else '❌'}")
            else:
                st.warning("검색 결과가 없습니다.")

        else:
            # 검색 + 수집 + 파싱 + 저장
            st.subheader("파이프라인 실행")

            progress_bar = st.progress(0)
            status_text = st.empty()
            result_container = st.container()

            def on_progress(completed: int, total: int, pmcid: str):
                progress_bar.progress(completed / total if total > 0 else 0)
                status_text.text(f"수집 중: {completed}/{total} ({pmcid})")

            async def run_pipeline():
                pipeline = Pipeline(config)
                return await pipeline.run(
                    query=query,
                    limit=limit,
                    max_concurrent=config.api.max_concurrent,
                    on_progress=on_progress,
                    save_to_db=save_to_db,
                    save_to_s3=save_to_s3,
                )

            with st.spinner("파이프라인 실행 중..."):
                result = asyncio.run(run_pipeline())

            progress_bar.progress(1.0)
            status_text.text("완료!")

            with result_container:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("전체", result.total)
                with col2:
                    st.metric("성공", result.success)
                with col3:
                    st.metric("실패", result.failed)

                if result.papers:
                    st.success(f"✅ {result.success}개 논문 수집 완료")

                    for i, paper in enumerate(result.papers[:5], 1):
                        with st.expander(f"{i}. {paper.title[:80]}...", expanded=i <= 2):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Paper ID:** `{paper.paper_id}`")
                                st.write(f"**PMID:** {paper.pmid or 'N/A'}")
                                st.write(f"**PMCID:** {paper.pmcid or 'N/A'}")
                            with col2:
                                st.write(f"**Year:** {paper.year or 'N/A'}")
                                st.write(f"**Journal:** {paper.journal or 'N/A'}")
                                st.write(f"**저자 수:** {len(paper.authors)}")

                            st.write(f"**섹션:** {', '.join(s.name for s in paper.sections)}")
                            st.write(f"**Canonical Text 길이:** {paper.canonical_text_length:,} chars")

                    if len(result.papers) > 5:
                        st.info(f"... 외 {len(result.papers) - 5}개")

                if result.errors:
                    with st.expander(f"⚠️ 오류 ({len(result.errors)}건)", expanded=False):
                        for err in result.errors:
                            st.error(f"**{err['pmcid']}:** {err['error']}")


# ========== 탭 2: 저장된 논문 ==========
with tab2:
    st.header("저장된 논문 목록")

    if st.button("🔄 새로고침", key="refresh_papers"):
        st.rerun()

    config = get_config()

    async def get_papers_list():
        db = DatabaseStorage(config)
        async with db.connect():
            count = await db.get_papers_count()
            papers = await db.get_papers(limit=50, offset=0)
            return count, papers

    try:
        with st.spinner("데이터 로딩 중..."):
            count, papers = asyncio.run(get_papers_list())

        st.info(f"총 {count}개 논문 저장됨")

        if papers:
            for paper in papers:
                with st.expander(
                    f"📄 {paper['title'][:60]}... ({paper['paper_id']})",
                    expanded=False
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Paper ID:** `{paper['paper_id']}`")
                        st.write(f"**PMID:** {paper.get('pmid') or 'N/A'}")
                        st.write(f"**PMCID:** {paper.get('pmcid') or 'N/A'}")
                    with col2:
                        st.write(f"**Year:** {paper.get('year') or 'N/A'}")
                        st.write(f"**Journal:** {paper.get('journal') or 'N/A'}")
                        st.write(f"**Source:** {paper.get('source')}")
                    with col3:
                        st.write(f"**Text Length:** {paper.get('canonical_text_length', 0):,} chars")
                        created_at = paper.get('created_at')
                        if created_at:
                            st.write(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M')}")

                    if paper.get('source_url'):
                        st.markdown(f"[📎 원본 보기]({paper['source_url']})")

        else:
            st.info("저장된 논문이 없습니다. '검색 & 수집' 탭에서 논문을 수집하세요.")

    except Exception as e:
        st.error(f"데이터베이스 연결 실패: {e}")
        st.info("Docker Compose로 데이터베이스를 시작하세요:")
        st.code("docker compose -f docker/docker-compose.yml up -d")


# ========== 탭 3: 논문 상세 ==========
with tab3:
    st.header("논문 상세 보기")

    paper_id = st.text_input(
        "Paper ID 입력",
        placeholder="예: pmid:27959700",
    )

    if paper_id and st.button("조회", key="view_paper"):
        config = get_config()

        async def get_paper_detail():
            db = DatabaseStorage(config)
            async with db.connect():
                return await db.get_paper_by_id(paper_id)

        try:
            with st.spinner("조회 중..."):
                paper = asyncio.run(get_paper_detail())

            if paper:
                st.success(f"✅ 논문 발견: {paper['title'][:60]}...")

                # 메타데이터
                st.subheader("📋 메타데이터")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Paper ID:** `{paper['paper_id']}`")
                    st.write(f"**PMID:** {paper.get('pmid') or 'N/A'}")
                    st.write(f"**PMCID:** {paper.get('pmcid') or 'N/A'}")
                    st.write(f"**DOI:** {paper.get('doi') or 'N/A'}")
                with col2:
                    st.write(f"**Year:** {paper.get('year') or 'N/A'}")
                    st.write(f"**Journal:** {paper.get('journal') or 'N/A'}")
                    st.write(f"**Source:** {paper.get('source')}")
                    st.write(f"**Open Access:** {'✅' if paper.get('is_open_access') else '❌'}")

                st.write(f"**Title:** {paper['title']}")

                if paper.get('abstract'):
                    with st.expander("📝 Abstract", expanded=False):
                        st.write(paper['abstract'])

                if paper.get('keywords'):
                    st.write(f"**Keywords:** {', '.join(paper['keywords'][:10])}")

                # S3 텍스트 조회
                st.subheader("📄 Canonical Text")
                s3 = S3Storage(config)

                try:
                    text = s3.get_text_by_paper_id(paper['paper_id'])
                    if text:
                        st.info(f"길이: {len(text):,} chars")
                        with st.expander("전문 보기", expanded=False):
                            st.text_area("Canonical Text", text[:10000], height=400, disabled=True)
                            if len(text) > 10000:
                                st.warning(f"... (생략됨, 전체 {len(text):,} chars)")
                    else:
                        st.warning("S3에서 텍스트를 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"S3 연결 실패: {e}")

                if paper.get('source_url'):
                    st.markdown(f"[📎 원본 보기]({paper['source_url']})")

            else:
                st.warning(f"Paper ID '{paper_id}'를 찾을 수 없습니다.")

        except Exception as e:
            st.error(f"조회 실패: {e}")


# Footer
st.divider()
st.caption("""
**OAR-9: 논문 수집 파이프라인**
- Europe PMC API → PostgreSQL + S3
- 통합: OAR-18 (API), OAR-19 (파싱), OAR-20 (스키마)
""")
