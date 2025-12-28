# Europe PMC API 수집 한계점

## Background

Europe PMC API를 통해 논문 전문(Full-text XML)을 대량 수집하는 과정에서 성능 병목을 발견했다.

## 문제점

### 1. API 응답 시간이 전체의 98%

논문 1개 처리 시 소요 시간 분포:

| 단계 | 소요 시간 | 비율 |
|------|----------|------|
| XML 수집 (API 호출) | ~5초 | 98% |
| XML 파싱 | ~50ms | 1% |
| DB 저장 | ~100ms | 1% |

**API 응답 대기가 절대적 병목**

### 2. 순차 처리의 한계

```python
# 기존 순차 처리
for paper in papers:
    xml = client.get_fulltext_xml(paper.pmcid)  # 5초 대기
    parsed = parse(xml)
    save(parsed)
```

- 100개 논문 = 100 × 5초 = **~500초 (8분 이상)**
- 1,000개 논문 = **~83분**
- 10,000개 논문 = **~14시간**

대량 수집 시 현실적이지 않은 시간.

## Findings

### 병목 원인

1. **네트워크 I/O 대기**: API 서버 응답까지 CPU는 idle 상태
2. **순차 실행**: 한 번에 하나의 요청만 처리
3. **Rate Limit 불명확**: Europe PMC는 공식 rate limit을 명시하지 않음

### 해결 방향

**병렬 처리 (asyncio)** 도입으로 네트워크 대기 시간 중첩:

```python
# 병렬 처리
async with AsyncEuropePMCClient(max_concurrent=5) as client:
    results = await client.get_fulltext_xml_batch(pmcids)
```

- 5개 동시 요청 시: 100개 논문 = ~100초 (5배 개선)
- 10개 동시 요청 시: 100개 논문 = ~50초 (10배 개선)

### 성능 비교

| 처리 방식 | 100개 | 1,000개 |
|----------|-------|---------|
| 순차 | ~500초 | ~83분 |
| 병렬 (5개) | ~100초 | ~17분 |
| 병렬 (10개) | ~50초 | ~8분 |
| 병렬 (50개) | ~20초 | ~2분 |

## 제한 사항

### API Rate Limit

- Europe PMC는 공식 rate limit을 명시하지 않음
- 과도한 요청 시 차단 가능성 있음
- 권장: `max_concurrent=50`, `delay=0.1초`

### 하드웨어는 병목이 아님

- CPU/메모리 사용량 낮음 (대부분 I/O 대기)
- vCPU 1개로도 동시 50개 처리 가능
- 더 빠르게 하려면 멀티 인스턴스 분산 필요

## Decision

- 병렬 처리 도입으로 5~25배 속도 개선
- `max_concurrent` 값을 UI에서 조절 가능하게 구현
- 대량 수집 시 멀티 인스턴스 분산 전략 검토 필요

## 관련 구현

이 문제는 **OAR-19**에서 해결했다.

### 구현 위치

```
spikes/OAR-19/yts/
├── src/
│   ├── europe_pmc_client.py  # AsyncEuropePMCClient 추가
│   └── pipeline.py           # AsyncPipeline 추가
└── demo_app.py               # 병렬 처리 UI 적용
```

### 주요 변경

1. **AsyncEuropePMCClient** (`europe_pmc_client.py`)
   - `asyncio.Semaphore`로 동시 요청 수 제한
   - `get_fulltext_xml_batch()`: 여러 논문 병렬 수집

2. **AsyncPipeline** (`pipeline.py`)
   - `run_batch()`: 검색 → 수집 → 파싱 → 저장 병렬 처리
   - DB 연결 풀 재사용 (pool is closing 에러 해결)

3. **demo_app.py**
   - `max_concurrent` UI에서 조절 가능
   - 진행률 실시간 표시

### 참고

OAR-19 코드를 실행하여 병렬 처리 성능을 직접 확인할 수 있다:

```bash
cd spikes/OAR-19/yts
docker compose -f docker/docker-compose.yml up -d
uv run streamlit run demo_app.py
```
