# 임베딩 파이프라인 설계

> **상태**: 계획 수립
> **작성일**: 2025-12-31
> **관련**: Admin + Batch 연동

---

## 1. 현재 구조

```
[Admin 트리거]              [Celery Beat]
      │                          │
      ▼                          ▼
┌─────────────┐            ┌─────────────┐
│  Backfill   │            │   Embed     │
│  (수집)     │            │ (매시 정각)  │
└──────┬──────┘            └──────┬──────┘
       │                          │
       ▼                          ▼
   papers 저장              papers 조회
   (embedding_status        (IS NULL → 임베딩)
    = NULL)
```

**문제점**: 수집 → 임베딩 사이 최대 1시간 지연

---

## 2. 목표 구조

### 2.1 체이닝 방식 (메인 흐름)

```
수집 트리거 ──▶ Backfill ──▶ Embed (체이닝)
                 완료          자동 트리거
                  │                │
                  ▼                ▼
              papers 저장     papers 임베딩
```

**모든 수집 태스크 → 임베딩 체이닝:**

| 수집 태스크 | 설명 | 체이닝 |
|-------------|------|--------|
| `backfill` | 초기 적재 | → `embed` |
| `incremental` | 일일 증분 수집 | → `embed` |
| `repair` | 실패 논문 재수집 | → `embed` |

### 2.2 Beat 스케줄 (보조/안전망)

```
[Beat 매시간] ──▶ Embed
                   │
                   └── embedding_status IS NULL 처리
                       (놓친 것, 실패 후 재시도 대상)
```

| 스케줄 | 주기 | 역할 |
|--------|------|------|
| `embed-hourly` | 매시 정각 | 누락분 처리 |
| `reembed-daily` | 매일 03:00 | 실패 논문 재시도 |

---

## 3. 구현 계획

### 3.1 Phase 1: Backfill → Embed 체이닝

**파일**: `batch/src/tasks/backfill.py`

```python
from .embed import run_embed

@app.task(bind=True, queue="backfill")
def run_backfill(self, query_id: str) -> dict:
    result = asyncio.run(run_backfill_async(query_id))

    # 수집 성공 시 임베딩 트리거
    if result.get("completed", 0) > 0:
        run_embed.delay(query_id)
        logger.info("embed_triggered_after_backfill", query_id=query_id)

    return result
```

- [x] `run_backfill` 완료 후 `run_embed.delay()` 호출
- [x] `run_backfill_resume`도 동일하게 적용

### 3.2 Phase 2: Incremental → Embed 체이닝

**파일**: `batch/src/tasks/incremental.py` (신규)

```python
@app.task(bind=True, queue="incremental")
def run_incremental(self, query_id: str) -> dict:
    result = asyncio.run(run_incremental_async(query_id))

    if result.get("completed", 0) > 0:
        run_embed.delay(query_id)

    return result
```

- [ ] incremental 태스크 구현
- [ ] 완료 후 embed 체이닝

### 3.3 Phase 3: Repair → Embed 체이닝

**파일**: `batch/src/tasks/repair.py` (신규)

- [ ] repair 태스크 구현
- [ ] 완료 후 embed 체이닝

---

## 4. Beat 스케줄 유지

**파일**: `batch/src/celery_app.py`

```python
beat_schedule = {
    # 안전망: 매시간 누락분 처리
    "embed-hourly": {
        "task": "src.tasks.embed.run_embed",
        "schedule": crontab(minute=0),
        "args": [None, 50],
        "options": {"queue": "embed"},
    },
    # 안전망: 매일 실패 재시도
    "reembed-daily": {
        "task": "src.tasks.embed.run_reembed",
        "schedule": crontab(hour=3, minute=0),
        "args": [None, None],
        "options": {"queue": "embed"},
    },
    # TODO: 증분 수집 스케줄 추가
    # "incremental-daily": {
    #     "task": "src.tasks.incremental.run_incremental",
    #     "schedule": crontab(hour=2, minute=0),
    #     ...
    # },
}
```

---

## 5. 데이터 흐름 최종

```
┌─────────────────────────────────────────────────────────────────┐
│                        메인 흐름 (체이닝)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Admin UI                                                       │
│     │                                                           │
│     ▼                                                           │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Backfill │───▶│  papers  │───▶│  Embed   │───▶│ Weaviate │  │
│  │          │    │ (저장)   │    │ (체이닝) │    │ (벡터)   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                 │
│  ┌──────────┐                    ┌──────────┐                   │
│  │Incremental│──────────────────▶│  Embed   │───▶ ...          │
│  └──────────┘                    └──────────┘                   │
│                                                                 │
│  ┌──────────┐                    ┌──────────┐                   │
│  │  Repair  │───────────────────▶│  Embed   │───▶ ...          │
│  └──────────┘                    └──────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      보조 흐름 (Beat 안전망)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Beat 매시간 ──▶ Embed ──▶ embedding_status IS NULL 처리        │
│                                                                 │
│  Beat 매일 03시 ──▶ Reembed ──▶ 실패(failed) 재시도             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 체크리스트

### Phase 1: Backfill 체이닝 (완료)
- [x] `backfill.py`에서 `run_embed.delay()` 호출 추가
- [x] `run_backfill_resume`에도 동일 적용
- [ ] 테스트: 수집 완료 → 임베딩 자동 실행 확인

### Phase 2: Incremental 구현
- [ ] `incremental.py` 태스크 생성
- [ ] watermarks 테이블 활용
- [ ] 완료 후 embed 체이닝
- [ ] Beat 스케줄 추가 (매일 02:00)

### Phase 3: Repair 구현
- [ ] `repair.py` 태스크 생성
- [ ] 실패 논문 재수집 로직
- [ ] 완료 후 embed 체이닝

### 기타
- [ ] Admin에서 incremental/repair 트리거 API 추가
- [ ] 문서 업데이트

---

## 7. 참고

### 관련 파일
- `batch/src/tasks/backfill.py` - 수집 태스크
- `batch/src/tasks/embed.py` - 임베딩 태스크
- `batch/src/celery_app.py` - Beat 스케줄

### 관련 문서
- `docs/admin-architecture.md` - 전체 아키텍처
- `docs/service-plan.md` - 서비스 계획
