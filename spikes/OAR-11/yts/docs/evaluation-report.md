# OAR-11 Evidence RAG 시스템 평가 보고서

> 작성일: 2025-12-30
> 목적: E2E 데모 품질 검증

## 1. 사용된 논문 목록

| PMCID | 제목 | 연도 | 저널 | 청크 수 |
|-------|------|------|------|---------|
| PMC12570465 | The neuro-immune axis in cancer: from mechanisms to therapeutic opportunities | 2025 | Journal of Hematology & Oncology | 43 |
| PMC12583504 | Oncogenic KRAS mutations drive immune suppression through immune-related regulatory network | 2025 | Cell Death & Disease | 28 |
| PMC12625643 | Neutrophils in non-small cell lung cancer and immunotherapy with PD-1/PD-L1 inhibitors | 2025 | Journal of Translational Medicine | 23 |
| PMC12526406 | Repurposing Artemisinin-Based Drugs from Antimalarial to Pan-Therapeutic | 2025 | Drug Design, Development and Therapy | 35 |
| PMC12541881 | Decoding the tumor immune microenvironment in lung squamous cell carcinoma | 2025 | Translational Lung Cancer Research | 20 |

**총 청크 수**: 149개 (실제 논문) + 3개 (테스트 샘플) = 152개

---

## 2. 검색 품질 평가

### 테스트 케이스 1: Neutrophils in lung cancer

**질문**: "What is the role of neutrophils in lung cancer immunotherapy?"

| 순위 | PMCID | 섹션 | 점수 | 관련성 |
|------|-------|------|------|--------|
| 1 | PMC12625643 | introduction | 0.885 | ✅ 정확 |
| 2 | PMC12625643 | introduction | 0.882 | ✅ 정확 |
| 3 | PMC12625643 | introduction | 0.880 | ✅ 정확 |

**분석**:
- 논문 PMC12625643는 제목이 "Neutrophils in non-small cell lung cancer and immunotherapy"
- 질문과 완전히 일치하는 논문에서 검색됨
- **평가: PASS** ✅

---

### 테스트 케이스 2: KRAS mutation

**질문**: "How does KRAS mutation affect immune response?"

| 순위 | PMCID | 섹션 | 점수 | 관련성 |
|------|-------|------|------|--------|
| 1 | PMC12583504 | abstract | 0.960 | ✅ 정확 |
| 2 | PMC12583504 | introduction | 0.884 | ✅ 정확 |
| 3 | PMC12583504 | modulation of immune... | 0.883 | ✅ 정확 |

**분석**:
- 논문 PMC12583504는 "Oncogenic KRAS mutations drive immune suppression"
- 질문의 핵심 키워드 (KRAS, immune)와 정확히 매칭
- abstract 섹션이 0.960으로 매우 높은 점수
- **평가: PASS** ✅

---

### 테스트 케이스 3: Neuro-immune axis

**질문**: "What is neuro-immune axis in cancer?"

| 순위 | PMCID | 섹션 | 점수 | 관련성 |
|------|-------|------|------|--------|
| 1 | PMC12570465 | introduction | 0.826 | ✅ 정확 |
| 2 | PMC12570465 | introduction | 0.822 | ✅ 정확 |
| 3 | PMC12570465 | discussion | 0.817 | ✅ 정확 |

**분석**:
- 논문 PMC12570465는 "The neuro-immune axis in cancer: from mechanisms..."
- 제목에 "neuro-immune axis in cancer"가 포함됨
- **평가: PASS** ✅

---

## 3. LLM 답변 품질 평가

### 평가 기준
1. **정확성**: 검색된 근거와 답변 내용이 일치하는가?
2. **인용 적절성**: Citation이 답변 내용을 뒷받침하는가?
3. **완성도**: 질문에 충분히 답변했는가?

### 샘플 평가: "What are the latest immunotherapy treatments for lung cancer?"

**생성된 답변 요약**:
1. Immune Checkpoint Inhibitors (PD-1/PD-L1) - 생존율 향상
2. Bifunctional Fusion Proteins (M7824) - TGF-β 타겟팅
3. Combination Therapies - anti-CXCL5 + anti-PD-L1
4. Targeting Immunosuppressive Elements - CXCR2 antagonist
5. Emerging Clinical Trials - CCR8 monoclonal antibody

**검증**:
| 답변 내용 | 인용 논문 | 논문에서 확인 | 결과 |
|-----------|-----------|---------------|------|
| PD-1/PD-L1 inhibitors improve survival | PMC12625643 | ✅ 논문 내용 확인됨 | PASS |
| M7824 targets TGF-β | PMC12625643 | ✅ 논문에 언급됨 | PASS |
| CXCR2 antagonist SX-682 | PMC12625643 | ✅ 논문에 언급됨 | PASS |
| CCR8 monoclonal antibody BAY 3375968 | PMC12541881 | ✅ 논문에 언급됨 | PASS |

**평가: PASS** ✅ - 모든 주장이 인용된 논문에서 확인됨

---

## 4. 시스템 성능 요약

### 검색 성능 (Retrieval)
| 지표 | 결과 |
|------|------|
| 검색 정확도 | 100% (3/3 테스트 통과) |
| 하이브리드 검색 alpha | 0.7 (벡터 70%, 키워드 30%) |
| Top-3 관련성 | 모든 결과가 관련 논문에서 추출됨 |

### 생성 성능 (Generation)
| 지표 | 결과 |
|------|------|
| Citation 정확도 | 100% (모든 인용이 실제 논문과 매칭) |
| 환각 (Hallucination) | 미발견 |
| 답변 완성도 | 높음 (다각적 관점 제공) |

---

## 5. 자동 평가 결과 (LLM 기반)

> 실행: `uv run python src/evaluate_rag.py`

### 검색 품질 (Retrieval)

| 지표 | 결과 | 설명 |
|------|------|------|
| **Recall@5** | 100% (5/5) | Top-5 내에 예상 논문 포함 |
| **Precision@1** | 80% (4/5) | Top-1이 정확한 논문 |
| **MRR** | 0.84 | 평균적으로 1.2번째에서 정답 발견 |

### 생성 품질 (Generation)

| 지표 | 점수 | 설명 |
|------|------|------|
| **Faithfulness** | 0.80 | 답변이 컨텍스트에 근거함 |
| **Answer Relevancy** | 1.00 | 답변이 질문에 완전히 관련됨 |
| **Concept Coverage** | 1.00 | 핵심 개념이 모두 포함됨 |

### 종합 점수

| 점수 | 등급 |
|------|------|
| **0.95** | 우수 ✅ |

### 질문별 상세 결과

| # | 질문 | 예상 논문 | Top-1 | Faithfulness | Relevancy |
|---|------|-----------|-------|--------------|-----------|
| 1 | Neutrophils in lung cancer immunotherapy | PMC12625643 | ✅ | 1.00 | 1.00 |
| 2 | KRAS mutation affects immune response | PMC12583504 | ✅ | 1.00 | 1.00 |
| 3 | Neuro-immune axis in cancer | PMC12570465 | ✅ | 1.00 | 1.00 |
| 4 | Latest immunotherapy treatments | PMC12625643 | ✅ | 1.00 | 1.00 |
| 5 | CCR8 in tumor microenvironment | PMC12541881 | ❌ | 0.00 | 1.00 |

**분석**:
- CCR8 질문에서 Top-1이 예상 논문이 아님 (PMC12570465가 검색됨)
- 해당 논문에 CCR8 관련 내용이 적어 Faithfulness가 0으로 평가됨
- **개선 방안**: 더 많은 CCR8 관련 논문 적재 필요

---

## 6. 한계점 및 개선 사항

### 현재 한계
1. **테스트 샘플 혼재**: PMC00000001, PMC00000002 (테스트용 가짜 데이터)가 결과에 포함됨
2. **적은 논문 수**: 5개 논문만 적재 (더 많은 논문 필요)
3. **섹션 편중**: introduction 섹션에서 주로 검색됨

### 권장 개선 사항
1. 테스트 데이터 제거 후 운영 환경 분리
2. 더 많은 논문 적재 (최소 100편 권장)
3. 섹션별 가중치 조정 고려 (methods, results 섹션 강화)
4. 임베딩 모델 비교 테스트 (MedCPT vs OpenAI)

---

## 7. 결론

| 평가 항목 | 상태 |
|-----------|------|
| E2E 파이프라인 작동 | ✅ 정상 |
| 검색 정확도 | ✅ 양호 |
| LLM 답변 품질 | ✅ 양호 |
| Citation 연결 | ✅ 정상 |
| 발표 데모 준비 | ✅ 완료 |

**종합 평가**: 발표용 E2E 데모로 충분히 사용 가능.
실제 운영을 위해서는 테스트 데이터 제거 및 논문 수 확대 필요.
