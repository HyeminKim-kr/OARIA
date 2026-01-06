# RAG 품질 개선 전략

> RAG Lab에서 수집된 데이터를 활용한 품질 개선 방안

---

## 1. 수집 데이터 현황

### lab_test_logs
| 필드 | 설명 |
|------|------|
| query | 테스트 쿼리 |
| test_type | search / generate / compare |
| parameters | limit, alpha, useReranker 등 |
| results | 검색된 chunks, 생성된 답변 |
| *_latency_ms | 검색/Rerank/LLM 소요시간 |

### lab_feedbacks
| 필드 | 설명 |
|------|------|
| query | 평가 대상 쿼리 |
| rating | good / bad |
| result_summary | topScore, totalChunks 등 |
| comment | 추가 코멘트 (선택) |

---

## 2. 자동화 가능 vs 불가능

### 자동 측정 가능
- 레이턴시 (검색, Rerank, LLM)
- 검색 점수 (score, rerank_score)
- 답변 길이, 토큰 수
- 검색 결과 개수

### 사람 판단 필요
- 답변의 **정확성**
- 검색 결과의 **실제 관련성**
- 질문 의도 **파악 여부**
- 답변의 **완결성**

> 핵심: "품질"의 정의 자체가 사람의 판단에 의존

---

## 3. 활용 단계

### 3.1 단기 (즉시 가능)

#### 파라미터 최적화 분석
```sql
-- 좋은 평가의 평균 파라미터
SELECT
  AVG((parameters->>'alpha')::float) as avg_alpha,
  AVG((parameters->>'limit')::int) as avg_limit,
  COUNT(*) FILTER (WHERE (parameters->>'useReranker')::boolean) as reranker_count
FROM lab_feedbacks
WHERE rating = 'good';
```

#### 실패 쿼리 패턴 분석
```sql
-- 나쁜 평가 쿼리 + 점수
SELECT
  query,
  (result_summary->>'topScore')::float as top_score
FROM lab_feedbacks
WHERE rating = 'bad'
ORDER BY created_at DESC;
```

**분석 포인트:**
- top_score 낮음 → 관련 문서 DB에 없음 → 데이터 보강
- top_score 높은데 bad → 답변 생성 문제 → 프롬프트 개선
- 특정 주제 집중 실패 → 해당 도메인 데이터 부족

### 3.2 중기 (2-4주)

#### Golden Dataset 구축
good 평가 + 높은 점수의 쿼리-답변 쌍 수집:

```python
golden_queries = [
    {
        "query": "What are the effects of...",
        "expected_paper_ids": ["PMC123", "PMC456"],
        "expected_keywords": ["keyword1", "keyword2"]
    }
]
```

**용도:**
- 코드 변경 후 regression 테스트
- 새 파라미터 A/B 테스트
- 임베딩 모델 변경 시 비교

#### 쿼리 유형별 파라미터 최적화
| 쿼리 유형 | 권장 alpha | 권장 limit | Reranker |
|----------|-----------|-----------|----------|
| 정의/개념 질문 | 0.8 | 5 | ON |
| 특정 논문 검색 | 0.3 | 10 | OFF |
| 비교/분석 | 0.7 | 15 | ON |

### 3.3 장기 (1-3개월)

#### Active Learning Pipeline
```
1. 쿼리 → 검색 → 답변
2. 자동 confidence 점수 계산
3. 낮은 confidence → 관리자 리뷰 큐
4. 리뷰 결과 반영
5. 모델/데이터 개선
```

#### LLM-as-Judge (반자동 평가)
- GPT-4로 답변 품질 자동 평가
- 사람보다 일관성 있음
- 단, Golden Set 검증은 사람 필요

---

## 4. 피드백 루프

```
사람 피드백
     ↓
Golden Dataset 구축
     ↓
자동 평가 파이프라인 구축
     ↓
자동 평가로 빠른 반복
     ↓
주기적 사람 검증 (drift 방지)
     ↓
(반복)
```

---

## 5. 권장 실행 순서

| 우선순위 | 작업 | 담당 | 기대 효과 |
|---------|------|------|----------|
| 1 | 주간 bad 피드백 리뷰 | 도메인 전문가 | 즉시 문제 파악 |
| 2 | Golden Dataset 50개 | 도메인 전문가 | regression 방지 |
| 3 | 파라미터별 성공률 대시보드 | 개발 | 최적값 도출 |
| 4 | 실패 쿼리 → 데이터 보강 | 데이터팀 | 커버리지 확대 |

---

## 6. 추가 수집 권장 데이터

현재 피드백에 추가하면 개선 방향이 명확해지는 필드:

```typescript
// 실패 이유 분류
failureReason?:
  | 'no_relevant_docs'    // 관련 문서 없음
  | 'wrong_answer'        // 답변 오류
  | 'incomplete'          // 불완전한 답변
  | 'too_verbose'         // 너무 장황
  | 'off_topic';          // 주제 벗어남

// 사용자 수정 답변 (선택)
correctedAnswer?: string;

// 실제 관련 있던 chunk 선택 (선택)
relevantChunkIds?: string[];
```

---

## 7. 핵심 원칙

1. **처음엔 사람이 해야 한다** - 자동화는 사람 판단 기준이 쌓인 후
2. **작게 시작** - 주 10-20개 리뷰로 시작
3. **피드백 루프를 닫아라** - 수집 → 분석 → 개선 → 재측정
4. **Golden Set이 핵심 자산** - 이게 있어야 자동화 가능

---

## 참고

- Lab 페이지: `/admin/lab`
- 통계 API: `GET /lab/stats/feedback`, `GET /lab/stats/logs`
- 관련 테이블: `lab_test_logs`, `lab_feedbacks`
