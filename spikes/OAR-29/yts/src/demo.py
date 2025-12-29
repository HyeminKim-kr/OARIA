"""청킹 시각화 데모

HTML로 청킹 과정을 단계별로 시각화
팀원에게 설명하기 위한 데모용
"""

import html
import re
import sys
from datetime import datetime
from pathlib import Path

# 같은 src 폴더의 chunker 모듈 사용
sys.path.insert(0, str(Path(__file__).parent))

from chunker import ChunkingResult, TextChunker


def generate_html_report(result: ChunkingResult, verifications: list[dict]) -> str:
    """청킹 결과를 HTML 리포트로 생성"""

    # 색상 팔레트 (섹션별)
    section_colors = {
        "abstract": "#e3f2fd",
        "introduction": "#f3e5f5",
        "methods": "#e8f5e9",
        "results": "#fff3e0",
        "discussion": "#fce4ec",
        "conclusion": "#e0f7fa",
        "unknown": "#f5f5f5",
    }

    # 검증 결과 요약
    valid_count = sum(1 for v in verifications if v["valid"])
    total_count = len(verifications)

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OAR-29: 청킹 시각화 데모</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 2rem;
            margin-bottom: 2rem;
            border-radius: 1rem;
        }}
        header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        header p {{
            opacity: 0.9;
        }}
        .step {{
            background: white;
            border-radius: 1rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }}
        .step-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #e2e8f0;
        }}
        .step-number {{
            background: #667eea;
            color: white;
            width: 3rem;
            height: 3rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.25rem;
        }}
        .step-title {{
            font-size: 1.5rem;
            font-weight: 600;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .stat-card {{
            background: #f1f5f9;
            padding: 1.25rem;
            border-radius: 0.75rem;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #64748b;
            font-size: 0.875rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: #475569;
        }}
        tr:hover {{
            background: #f8fafc;
        }}
        .section-tag {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .chunk-preview {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            background: #f1f5f9;
            padding: 0.5rem;
            border-radius: 0.5rem;
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .fulltext-preview {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            background: #1e293b;
            color: #e2e8f0;
            padding: 1.5rem;
            border-radius: 0.75rem;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .highlight {{
            background: #fef08a;
            padding: 0 2px;
            border-radius: 2px;
        }}
        .section-block {{
            margin-bottom: 1rem;
            border-left: 4px solid;
            padding-left: 1rem;
        }}
        .valid {{
            color: #16a34a;
        }}
        .invalid {{
            color: #dc2626;
        }}
        .chunk-card {{
            background: #f8fafc;
            border-radius: 0.75rem;
            padding: 1rem;
            margin-bottom: 1rem;
            border-left: 4px solid #667eea;
        }}
        .chunk-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }}
        .chunk-id {{
            font-weight: 600;
            font-family: monospace;
        }}
        .chunk-meta {{
            display: flex;
            gap: 1rem;
            font-size: 0.875rem;
            color: #64748b;
        }}
        .chunk-text {{
            font-size: 0.875rem;
            color: #475569;
            background: white;
            padding: 1rem;
            border-radius: 0.5rem;
            max-height: 150px;
            overflow-y: auto;
        }}
        .tabs {{
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }}
        .tab {{
            padding: 0.5rem 1rem;
            border: none;
            background: #e2e8f0;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 500;
        }}
        .tab.active {{
            background: #667eea;
            color: white;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .verification-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .verification-badge.pass {{
            background: #dcfce7;
            color: #16a34a;
        }}
        .verification-badge.fail {{
            background: #fee2e2;
            color: #dc2626;
        }}
        .flow-diagram {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            padding: 2rem;
            background: #f8fafc;
            border-radius: 0.75rem;
            margin: 1rem 0;
            flex-wrap: wrap;
        }}
        .flow-box {{
            background: white;
            padding: 1rem 1.5rem;
            border-radius: 0.5rem;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 120px;
        }}
        .flow-arrow {{
            font-size: 1.5rem;
            color: #667eea;
        }}
        footer {{
            text-align: center;
            padding: 2rem;
            color: #64748b;
            font-size: 0.875rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>OAR-29: 텍스트 청킹 시각화 데모</h1>
            <p>논문 전문을 RAG 검색에 최적화된 청크로 분할하는 과정</p>
            <p style="margin-top: 0.5rem; font-size: 0.875rem; opacity: 0.8;">
                생성 시각: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
        </header>

        <!-- Step 1: 원본 데이터 -->
        <div class="step">
            <div class="step-header">
                <div class="step-number">1</div>
                <div class="step-title">원본 Fulltext 로드</div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{result.paper_id.split(':')[-1][:12]}</div>
                    <div class="stat-label">Paper ID</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{result.total_chars:,}</div>
                    <div class="stat-label">총 문자 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{result.total_tokens:,}</div>
                    <div class="stat-label">총 토큰 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(result.sections)}</div>
                    <div class="stat-label">섹션 수</div>
                </div>
            </div>

            <h4 style="margin-bottom: 0.5rem;">논문 제목</h4>
            <p style="color: #475569; margin-bottom: 1rem;">{html.escape(result.title)}</p>

            <h4 style="margin-bottom: 0.5rem;">Fulltext 미리보기 (처음 2000자)</h4>
            <div class="fulltext-preview">{html.escape(result.fulltext[:2000])}{'...' if len(result.fulltext) > 2000 else ''}</div>
        </div>

        <!-- Step 2: 섹션 분리 -->
        <div class="step">
            <div class="step-header">
                <div class="step-number">2</div>
                <div class="step-title">섹션 분리</div>
            </div>

            <div class="flow-diagram">
                <div class="flow-box">
                    <div style="font-size: 2rem;">📄</div>
                    <div>Fulltext</div>
                </div>
                <div class="flow-arrow">→</div>
                <div class="flow-box">
                    <div style="font-size: 2rem;">✂️</div>
                    <div>섹션 분리</div>
                </div>
                <div class="flow-arrow">→</div>
                {' '.join([f'<div class="flow-box" style="border-top: 3px solid {section_colors.get(s.name, section_colors["unknown"])}"><div style="font-size: 1.5rem;">📑</div><div>{s.name}</div></div>' for s in result.sections[:5]])}
            </div>

            <table>
                <thead>
                    <tr>
                        <th>순서</th>
                        <th>섹션</th>
                        <th>길이 (문자)</th>
                        <th>Offset 범위</th>
                        <th>미리보기</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{i+1}</td>
                        <td><span class="section-tag" style="background: {section_colors.get(s.name, section_colors['unknown'])}">{s.name}</span></td>
                        <td>{len(s.text):,}자</td>
                        <td><code>{s.offset_start:,} ~ {s.offset_end:,}</code></td>
                        <td><div class="chunk-preview">{html.escape(s.text[:80])}...</div></td>
                    </tr>
                    ''' for i, s in enumerate(result.sections)])}
                </tbody>
            </table>
        </div>

        <!-- Step 3: 청킹 -->
        <div class="step">
            <div class="step-header">
                <div class="step-number">3</div>
                <div class="step-title">섹션별 Recursive Chunking</div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{len(result.chunks)}</div>
                    <div class="stat-label">총 청크 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{result.avg_chunk_tokens:.0f}</div>
                    <div class="stat-label">평균 토큰/청크</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">700</div>
                    <div class="stat-label">목표 토큰</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">100</div>
                    <div class="stat-label">오버랩 토큰</div>
                </div>
            </div>

            <h4 style="margin: 1rem 0;">섹션별 청크 분포</h4>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
                {_generate_section_chunk_distribution(result)}
            </div>

            <h4 style="margin: 1rem 0;">청크 상세</h4>
            <div class="tabs">
                {_generate_section_tabs(result)}
            </div>

            {_generate_section_chunks_html(result, section_colors)}
        </div>

        <!-- Step 4: Offset 검증 -->
        <div class="step">
            <div class="step-header">
                <div class="step-number">4</div>
                <div class="step-title">Offset 검증 (근거 재현 테스트)</div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" style="color: {'#16a34a' if valid_count == total_count else '#dc2626'}">{valid_count}/{total_count}</div>
                    <div class="stat-label">검증 통과</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{'✅' if valid_count == total_count else '❌'}</div>
                    <div class="stat-label">{'모든 offset 정확' if valid_count == total_count else 'offset 불일치 있음'}</div>
                </div>
            </div>

            <p style="margin: 1rem 0; color: #64748b;">
                각 청크의 <code>offset_start</code>와 <code>offset_end</code>로 원문에서 추출한 텍스트가
                저장된 청크 텍스트와 일치하는지 검증합니다.
            </p>

            <div style="background: #f1f5f9; padding: 1rem; border-radius: 0.5rem; font-family: monospace; font-size: 0.875rem;">
                <div style="color: #64748b; margin-bottom: 0.5rem;"># 검증 로직</div>
                <div>extracted = fulltext[chunk.offset_start : chunk.offset_end]</div>
                <div>assert extracted == chunk.text  <span style="color: #16a34a;"># ✅ 통과</span></div>
            </div>

            <h4 style="margin: 1.5rem 0 1rem;">검증 결과 샘플 (처음 10개)</h4>
            <table>
                <thead>
                    <tr>
                        <th>Chunk ID</th>
                        <th>Offset</th>
                        <th>결과</th>
                        <th>저장된 텍스트</th>
                        <th>추출된 텍스트</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td><code>{v["chunk_id"]}</code></td>
                        <td><code>{v["offset_start"]:,} ~ {v["offset_end"]:,}</code></td>
                        <td><span class="verification-badge {"pass" if v["valid"] else "fail"}">{"✅ PASS" if v["valid"] else "❌ FAIL"}</span></td>
                        <td><div class="chunk-preview">{html.escape(v["stored_preview"])}</div></td>
                        <td><div class="chunk-preview">{html.escape(v["extracted_preview"])}</div></td>
                    </tr>
                    ''' for v in verifications[:10]])}
                </tbody>
            </table>
        </div>

        <!-- Step 5: 최종 요약 -->
        <div class="step">
            <div class="step-header">
                <div class="step-number">5</div>
                <div class="step-title">최종 요약</div>
            </div>

            <div class="flow-diagram" style="background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%);">
                <div class="flow-box">
                    <div style="font-size: 2rem;">📄</div>
                    <div style="font-weight: 600;">{result.total_chars:,}자</div>
                    <div style="font-size: 0.75rem; color: #64748b;">원본 Fulltext</div>
                </div>
                <div class="flow-arrow">→</div>
                <div class="flow-box">
                    <div style="font-size: 2rem;">📑</div>
                    <div style="font-weight: 600;">{len(result.sections)}개</div>
                    <div style="font-size: 0.75rem; color: #64748b;">섹션</div>
                </div>
                <div class="flow-arrow">→</div>
                <div class="flow-box">
                    <div style="font-size: 2rem;">✂️</div>
                    <div style="font-weight: 600;">{len(result.chunks)}개</div>
                    <div style="font-size: 0.75rem; color: #64748b;">청크</div>
                </div>
                <div class="flow-arrow">→</div>
                <div class="flow-box" style="border: 2px solid #16a34a;">
                    <div style="font-size: 2rem;">{'✅' if valid_count == total_count else '⚠️'}</div>
                    <div style="font-weight: 600;">{valid_count}/{total_count}</div>
                    <div style="font-size: 0.75rem; color: #64748b;">Offset 검증</div>
                </div>
            </div>

            <h4 style="margin: 1.5rem 0 1rem;">청킹 설정</h4>
            <table>
                <tbody>
                    <tr><td><strong>청킹 전략</strong></td><td>Section + Recursive Character Text Splitter</td></tr>
                    <tr><td><strong>목표 청크 크기</strong></td><td>700 토큰 (600-800 범위)</td></tr>
                    <tr><td><strong>오버랩</strong></td><td>100 토큰 (~14%)</td></tr>
                    <tr><td><strong>분할 우선순위</strong></td><td><code>["\\n\\n", "\\n", ". ", " "]</code></td></tr>
                    <tr><td><strong>Offset 기준</strong></td><td>char index (UTF-8 decoded str)</td></tr>
                </tbody>
            </table>

            <h4 style="margin: 1.5rem 0 1rem;">다음 단계</h4>
            <ul style="list-style: none; padding: 0;">
                <li style="padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;">
                    <span style="margin-right: 0.5rem;">1️⃣</span>
                    임베딩 생성 (<code>[TITLE][SECTION][TEXT]</code> prefix 적용)
                </li>
                <li style="padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;">
                    <span style="margin-right: 0.5rem;">2️⃣</span>
                    Weaviate에 청크 + 벡터 저장
                </li>
                <li style="padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;">
                    <span style="margin-right: 0.5rem;">3️⃣</span>
                    검색 시 Parent 확장 (S3에서 ±500자)
                </li>
                <li style="padding: 0.5rem 0;">
                    <span style="margin-right: 0.5rem;">4️⃣</span>
                    LLM 답변 생성 + 근거 하이라이트
                </li>
            </ul>
        </div>

        <footer>
            <p>OAR-29: 텍스트 Chunker 구현 | OAR-11 Evidence RAG 시스템</p>
            <p>Generated by chunking demo script</p>
        </footer>
    </div>

    <script>
        function showSection(sectionName) {{
            // 모든 탭 비활성화
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

            // 선택된 탭 활성화
            event.target.classList.add('active');
            document.getElementById('section-' + sectionName).classList.add('active');
        }}
    </script>
</body>
</html>
"""
    return html_content


def _generate_section_tabs(result: ChunkingResult) -> str:
    """섹션별 탭 버튼 생성"""
    tabs = []
    for i, s in enumerate(result.sections):
        active_class = " active" if i == 0 else ""
        chunk_count = len([c for c in result.chunks if c.section == s.name])
        tabs.append(
            f'<button class="tab{active_class}" '
            f"onclick=\"showSection('{s.name}')\">"
            f'{s.name} ({chunk_count})</button>'
        )
    return ''.join(tabs)


def _generate_section_chunk_distribution(result: ChunkingResult) -> str:
    """섹션별 청크 분포 시각화"""
    section_colors = {
        "abstract": "#e3f2fd",
        "introduction": "#f3e5f5",
        "methods": "#e8f5e9",
        "results": "#fff3e0",
        "discussion": "#fce4ec",
        "conclusion": "#e0f7fa",
        "unknown": "#f5f5f5",
    }

    html_parts = []
    for section in result.sections:
        chunk_count = len([c for c in result.chunks if c.section == section.name])
        color = section_colors.get(section.name, section_colors["unknown"])
        html_parts.append(
            f'<div style="background: {color}; padding: 0.5rem 1rem; border-radius: 0.5rem;">'
            f'<span style="font-weight: 600;">{section.name}</span>: {chunk_count}개</div>'
        )
    return "".join(html_parts)


def _generate_section_chunks_html(result: ChunkingResult, section_colors: dict) -> str:
    """섹션별 청크 상세 HTML"""
    html_parts = []

    for i, section in enumerate(result.sections):
        section_chunks = [c for c in result.chunks if c.section == section.name]
        color = section_colors.get(section.name, section_colors["unknown"])

        chunks_html = ""
        for chunk in section_chunks:
            chunks_html += f'''
            <div class="chunk-card" style="border-left-color: {color.replace('fd', '99').replace('f5', '99').replace('e9', '99').replace('e0', '99').replace('ec', '99').replace('fa', '99')}">
                <div class="chunk-card-header">
                    <span class="chunk-id">{chunk.chunk_id}</span>
                    <div class="chunk-meta">
                        <span>🔢 {chunk.token_count} 토큰</span>
                        <span>📍 {chunk.offset_start:,} ~ {chunk.offset_end:,}</span>
                    </div>
                </div>
                <div class="chunk-text">{html.escape(chunk.text[:500])}{'...' if len(chunk.text) > 500 else ''}</div>
            </div>
            '''

        html_parts.append(
            f'<div id="section-{section.name}" class="tab-content{" active" if i == 0 else ""}">'
            f'{chunks_html}</div>'
        )

    return "".join(html_parts)


def run_demo_with_sample():
    """샘플 데이터로 데모 실행"""

    # 샘플 논문 데이터 (실제로는 MinIO에서 가져옴)
    sample_fulltext = """[TITLE] Immunotherapy Response Prediction in Non-Small Cell Lung Cancer Using Machine Learning

[ABSTRACT]
Background: Immune checkpoint inhibitors have revolutionized the treatment of non-small cell lung cancer (NSCLC). However, only a subset of patients respond to these therapies. Identifying predictive biomarkers is crucial for patient selection.

Methods: We analyzed data from 500 NSCLC patients treated with pembrolizumab or nivolumab between 2018 and 2023. Machine learning models were trained to predict treatment response based on clinical and molecular features.

Results: Our random forest model achieved an AUC of 0.85 for predicting treatment response. PD-L1 expression, tumor mutational burden, and smoking history were the most important features.

Conclusions: Machine learning can effectively predict immunotherapy response in NSCLC patients, potentially improving patient selection and treatment outcomes.

[INTRODUCTION]
Non-small cell lung cancer (NSCLC) accounts for approximately 85% of all lung cancer cases and remains a leading cause of cancer-related mortality worldwide. The introduction of immune checkpoint inhibitors (ICIs), particularly those targeting the PD-1/PD-L1 pathway, has significantly improved outcomes for patients with advanced NSCLC.

Despite the remarkable success of immunotherapy, only 20-30% of unselected NSCLC patients respond to ICI monotherapy. This highlights the urgent need for predictive biomarkers to identify patients who are most likely to benefit from these treatments while sparing non-responders from potential toxicities and treatment delays.

PD-L1 expression, measured by immunohistochemistry, is currently the most widely used biomarker for selecting patients for ICI therapy. However, its predictive value is imperfect, as some PD-L1-negative patients respond to treatment while some PD-L1-high patients do not. Other potential biomarkers, including tumor mutational burden (TMB), microsatellite instability, and gene expression signatures, have shown promise but are not yet routinely used in clinical practice.

Machine learning approaches offer the potential to integrate multiple clinical and molecular variables to improve prediction accuracy. Several studies have demonstrated the feasibility of using machine learning for cancer outcome prediction, but few have focused specifically on immunotherapy response in NSCLC.

In this study, we developed and validated machine learning models to predict immunotherapy response in NSCLC patients using a comprehensive set of clinical and molecular features.

[METHODS]
Study Population and Data Collection

We conducted a retrospective analysis of 500 patients with advanced NSCLC who received first-line pembrolizumab or nivolumab at our institution between January 2018 and December 2023. Patients were eligible if they had histologically confirmed stage IIIB or IV NSCLC, had received at least two cycles of ICI therapy, and had available baseline clinical and molecular data.

Clinical variables collected included age, sex, smoking history, Eastern Cooperative Oncology Group (ECOG) performance status, histological subtype, and presence of brain metastases. Molecular features included PD-L1 expression (tumor proportion score), tumor mutational burden (mutations per megabase), and driver mutation status (EGFR, ALK, ROS1, KRAS).

Response Assessment

Treatment response was assessed using RECIST 1.1 criteria. Patients were classified as responders (complete response or partial response) or non-responders (stable disease or progressive disease) based on their best overall response within the first 6 months of treatment.

Machine Learning Model Development

We evaluated several machine learning algorithms, including logistic regression, random forest, gradient boosting, and support vector machines. The dataset was split into training (70%) and test (30%) sets, with stratification to maintain class balance.

Feature selection was performed using recursive feature elimination with cross-validation. Model hyperparameters were optimized using 5-fold cross-validation on the training set. Model performance was evaluated using area under the receiver operating characteristic curve (AUC), sensitivity, specificity, and F1 score.

Statistical Analysis

Continuous variables were compared using the Mann-Whitney U test, and categorical variables were compared using the chi-square test. All statistical analyses were performed using Python 3.9 with scikit-learn and scipy packages. A two-sided p-value < 0.05 was considered statistically significant.

[RESULTS]
Patient Characteristics

Of the 500 patients included in the analysis, 285 (57%) were male, and the median age was 65 years (range: 38-89). The majority of patients (72%) had adenocarcinoma histology, and 68% had a smoking history. PD-L1 expression was ≥50% in 35% of patients, 1-49% in 40%, and <1% in 25%.

After a median follow-up of 18 months, 165 patients (33%) achieved an objective response (15 complete responses, 150 partial responses), while 335 patients (67%) were classified as non-responders.

Model Performance

The random forest model achieved the best performance, with an AUC of 0.85 (95% CI: 0.81-0.89) on the test set. The gradient boosting model achieved an AUC of 0.83, while logistic regression and SVM achieved AUCs of 0.78 and 0.80, respectively.

At the optimal threshold, the random forest model achieved a sensitivity of 78%, specificity of 82%, positive predictive value of 68%, and negative predictive value of 88%.

Feature Importance

Analysis of feature importance revealed that PD-L1 expression was the most predictive variable, followed by tumor mutational burden, smoking history, ECOG performance status, and age. Interestingly, the combination of these features provided substantially better prediction than any single biomarker alone.

Subgroup Analysis

We performed subgroup analyses based on PD-L1 expression levels. In the PD-L1 ≥50% subgroup, the model achieved an AUC of 0.79. In the PD-L1 1-49% subgroup, the AUC was 0.82, and in the PD-L1 <1% subgroup, the AUC was 0.84. These results suggest that the model may be particularly useful in patients with low or intermediate PD-L1 expression.

Patients predicted to respond by the model had significantly longer progression-free survival (median 12.5 months vs. 4.2 months, HR 0.42, p<0.001) and overall survival (median 24.8 months vs. 11.3 months, HR 0.51, p<0.001) compared to patients predicted not to respond.

[DISCUSSION]
In this study, we developed and validated machine learning models to predict immunotherapy response in NSCLC patients. Our random forest model achieved an AUC of 0.85, outperforming single biomarkers such as PD-L1 expression alone.

The superior performance of our multi-variable model highlights the complex biology underlying immunotherapy response. While PD-L1 expression remains an important predictor, our results suggest that integrating additional clinical and molecular features can substantially improve prediction accuracy.

Our finding that the model performed well across all PD-L1 expression subgroups is particularly noteworthy. Current clinical practice often relies heavily on PD-L1 expression for treatment decisions, but this approach may miss responders among PD-L1-low patients and expose non-responders among PD-L1-high patients to unnecessary treatment. Our model could potentially complement PD-L1 testing to improve patient selection.

Several limitations of our study should be acknowledged. First, this was a retrospective, single-center study, and our results require validation in independent cohorts. Second, we did not include some potentially relevant biomarkers, such as gene expression signatures or circulating tumor DNA, due to data availability. Third, our definition of response was based on RECIST criteria, which may not fully capture the complexity of immunotherapy response patterns.

Future directions include prospective validation of our model, integration of additional biomarkers such as the tumor microenvironment features and circulating biomarkers, and development of models for predicting specific outcomes such as durable response and immune-related adverse events.

[CONCLUSION]
Machine learning can effectively predict immunotherapy response in NSCLC patients by integrating multiple clinical and molecular features. Our model could potentially improve patient selection for immunotherapy, leading to better outcomes and more efficient use of healthcare resources. Prospective validation studies are warranted before clinical implementation.
"""

    # 섹션 정보 추출 (실제로는 xml_parser에서 가져옴)
    sections = []
    section_pattern = r'\[([A-Z]+)\]'

    # 섹션 위치 찾기
    matches = list(re.finditer(section_pattern, sample_fulltext))
    for i, match in enumerate(matches):
        section_name = match.group(1).lower()
        start = match.end()

        # 다음 섹션 시작 또는 끝까지
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(sample_fulltext)

        # 섹션 텍스트 정리
        text = sample_fulltext[start:end].strip()
        if text:
            sections.append({
                "name": section_name,
                "title": section_name.title(),
                "offset_start": start,
                "offset_end": start + len(text),
            })

    # Chunker 생성 및 실행
    chunker = TextChunker(
        chunk_size_tokens=700,
        chunk_overlap_tokens=100,
        min_chunk_tokens=50,
    )

    result = chunker.chunk_paper(
        paper_id="pmc:PMC12345678",
        title="Immunotherapy Response Prediction in Non-Small Cell Lung Cancer Using Machine Learning",
        fulltext=sample_fulltext,
        sections=sections,
        year=2024,
    )

    # Offset 검증
    verifications = chunker.verify_offsets(result)

    # HTML 리포트 생성
    html_content = generate_html_report(result, verifications)

    # 파일 저장
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "chunking_demo.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ HTML 리포트 생성 완료: {output_path}")
    print(f"   - 총 청크 수: {len(result.chunks)}")
    print(f"   - 평균 토큰: {result.avg_chunk_tokens:.0f}")
    print(f"   - Offset 검증: {sum(1 for v in verifications if v['valid'])}/{len(verifications)} 통과")

    return output_path


# ============================================================
# 실제 데이터 연동 (PostgreSQL + MinIO)
# ============================================================

# DB/S3 설정 (spikes/yts/batch와 동일)
DB_CONFIG = {
    "host": "localhost",
    "port": 15432,
    "user": "oaria",
    "password": "oaria_dev_2024",
    "dbname": "oaria",
}

S3_CONFIG = {
    "endpoint_url": "http://localhost:19000",
    "aws_access_key_id": "minioadmin",
    "aws_secret_access_key": "minioadmin_2024",
    "bucket": "oaria-papers",
}


def fetch_papers_from_db(limit: int = 5) -> list[dict]:
    """PostgreSQL에서 논문 목록 조회"""
    import psycopg

    papers = []
    dsn = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # papers 테이블에서 조회
            cur.execute(
                """
                SELECT p.id, p.paper_id, p.title, p.year, p.canonical_prefix
                FROM papers p
                WHERE p.canonical_prefix IS NOT NULL
                ORDER BY p.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

            for row in rows:
                paper_uuid, paper_id, title, year, canonical_prefix = row

                # 섹션 정보 조회
                cur.execute(
                    """
                    SELECT section_name, section_title, section_order, offset_start, offset_end
                    FROM paper_sections
                    WHERE paper_id = %s
                    ORDER BY section_order
                    """,
                    (paper_uuid,),
                )
                sections = [
                    {
                        "name": s[0],
                        "title": s[1],
                        "order": s[2],
                        "offset_start": s[3],
                        "offset_end": s[4],
                    }
                    for s in cur.fetchall()
                ]

                papers.append({
                    "paper_id": paper_id,
                    "title": title,
                    "year": year,
                    "canonical_prefix": canonical_prefix,
                    "sections": sections,
                })

    return papers


def fetch_fulltext_from_s3(canonical_prefix: str) -> str | None:
    """MinIO에서 fulltext 조회"""
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=S3_CONFIG["endpoint_url"],
        aws_access_key_id=S3_CONFIG["aws_access_key_id"],
        aws_secret_access_key=S3_CONFIG["aws_secret_access_key"],
    )

    try:
        response = client.get_object(
            Bucket=S3_CONFIG["bucket"],
            Key=f"{canonical_prefix}/fulltext.txt",
        )
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def run_demo_with_real_data():
    """실제 수집된 논문으로 데모 실행"""
    print("📡 PostgreSQL + MinIO에서 실제 데이터 조회 중...")

    try:
        papers = fetch_papers_from_db(limit=3)

        if not papers:
            print("⚠️  수집된 논문이 없습니다. 샘플 데이터로 대체합니다.")
            return run_demo_with_sample()

        print(f"   - 조회된 논문: {len(papers)}개\n")

        # Chunker 생성
        chunker = TextChunker(
            chunk_size_tokens=700,
            chunk_overlap_tokens=100,
            min_chunk_tokens=50,
        )

        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)

        for i, paper in enumerate(papers, 1):
            print(f"[{i}/{len(papers)}] {paper['paper_id']}")
            print(f"         제목: {paper['title'][:60]}...")

            # fulltext 조회
            fulltext = fetch_fulltext_from_s3(paper["canonical_prefix"])
            if not fulltext:
                print("         ⚠️  fulltext 없음, 스킵")
                continue

            # 청킹 실행
            result = chunker.chunk_paper(
                paper_id=paper["paper_id"],
                title=paper["title"],
                fulltext=fulltext,
                sections=paper["sections"],
                year=paper["year"],
            )

            # Offset 검증
            verifications = chunker.verify_offsets(result)
            valid_count = sum(1 for v in verifications if v["valid"])

            # HTML 리포트 생성
            html_content = generate_html_report(result, verifications)

            # 파일명 생성 (paper_id에서 안전한 문자만)
            safe_name = paper["paper_id"].replace(":", "_").replace("/", "_")
            output_path = output_dir / f"chunking_{safe_name}.html"

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"         ✅ 청크: {len(result.chunks)}개, 평균 {result.avg_chunk_tokens:.0f} 토큰")
            print(f"         ✅ Offset 검증: {valid_count}/{len(verifications)} 통과")
            print(f"         📄 {output_path}\n")

        print("🎉 모든 데모 완료!")
        return output_dir

    except Exception as e:
        print(f"❌ 실제 데이터 조회 실패: {e}")
        print("   샘플 데이터로 대체합니다.\n")
        return run_demo_with_sample()


def run_demo_with_file(file_path: str):
    """로컬 fulltext 파일로 데모 실행"""
    print(f"📄 파일에서 데이터 로드: {file_path}")

    fulltext = Path(file_path).read_text(encoding="utf-8")
    print(f"   - 길이: {len(fulltext):,} chars\n")

    # [SECTION] 마커로 섹션 파싱
    section_pattern = r'\[([A-Z][A-Z0-9 _-]+)\]'
    matches = list(re.finditer(section_pattern, fulltext))

    print(f"📑 발견된 섹션: {len(matches)}개")

    sections = []
    for i, match in enumerate(matches):
        section_name = match.group(1).lower().replace(' ', '_')

        # 섹션 내용 시작 (마커 끝 + 줄바꿈 스킵)
        content_start = match.end()
        while content_start < len(fulltext) and fulltext[content_start] in '\n\r':
            content_start += 1

        # 다음 섹션 시작 또는 끝
        if i + 1 < len(matches):
            content_end = matches[i + 1].start()
        else:
            content_end = len(fulltext)

        # 끝 공백 제거
        while content_end > content_start and fulltext[content_end - 1] in '\n\r\t ':
            content_end -= 1

        content = fulltext[content_start:content_end]

        if content.strip():
            sections.append({
                'name': section_name,
                'title': match.group(1).title(),
                'offset_start': content_start,
                'offset_end': content_end,
            })
            print(f"   [{i+1:2}] {section_name[:35]:<35} | {content_start:>6} ~ {content_end:>6} | {len(content):>5} chars")

    print()

    # 파일명에서 paper_id 추출
    file_name = Path(file_path).stem
    paper_id = f"file:{file_name}"

    # Chunker 실행
    chunker = TextChunker(
        chunk_size_tokens=700,
        chunk_overlap_tokens=100,
        min_chunk_tokens=50,
    )

    result = chunker.chunk_paper(
        paper_id=paper_id,
        title=f"Paper from {file_name}",
        fulltext=fulltext,
        sections=sections,
        year=None,
    )

    # Offset 검증
    verifications = chunker.verify_offsets(result)
    valid_count = sum(1 for v in verifications if v["valid"])

    print(f"✂️  총 청크 수: {len(result.chunks)}")
    print(f"📊 평균 토큰: {result.avg_chunk_tokens:.0f}")
    print(f"🔍 Offset 검증: {valid_count}/{len(verifications)} 통과")

    # HTML 리포트 생성
    html_content = generate_html_report(result, verifications)

    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"chunking_{file_name}.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n📄 HTML 리포트: {output_path}")

    # 실패 케이스 출력
    failed = [v for v in verifications if not v["valid"]]
    if failed:
        print(f"\n❌ Offset 검증 실패 ({len(failed)}개):")
        for v in failed[:3]:
            print(f"   {v['chunk_id']}")
            print(f"   offset: {v['offset_start']} ~ {v['offset_end']}")
            print(f"   stored:    {repr(v['stored_preview'][:50])}")
            print(f"   extracted: {repr(v['extracted_preview'][:50])}")
            print()

    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OAR-29 청킹 시각화 데모")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="샘플 데이터 사용 (DB 연결 없이)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="로컬 fulltext 파일 경로 (예: docs/PMC12570465.txt)",
    )
    args = parser.parse_args()

    if args.file:
        run_demo_with_file(args.file)
    elif args.sample:
        run_demo_with_sample()
    else:
        run_demo_with_real_data()
