# OAR-29: 텍스트 Chunker 구현 (yts)

> **담당자**: yts
>
> **Sub-task**: OAR-29
>
> **상태**: 진행 중

---

## 접근 방식

기존 설계 문서(OAR-18, OAR-20)를 기반으로 **offset 추적이 가능한 Section + Recursive Chunker** 구현

### 핵심 결정

| 항목 | 값 |
|------|-----|
| 청크 크기 | 600-800 토큰 |
| 오버랩 | 10-15% (80-120 토큰) |
| 전략 | Section + Recursive |
| offset 기준 | char index (Python str) |

---

## 폴더 구조

```
yts/
├── README.md                           # 이 파일
├── docs/
│   └── chunker-implementation.md       # 상세 구현 설계
├── src/
│   └── chunker.py                      # Chunker 구현 (TODO)
├── output/
│   └── (청킹 결과물)
└── tests/
    └── test_chunker.py                 # 테스트 (TODO)
```

---

## How to Run

```bash
cd spikes/OAR-29/yts

# 환경 설정
uv sync

# Chunker 실행
uv run python src/chunker.py

# 테스트
uv run pytest tests/
```

---

## 상세 문서

- [Chunker 구현 설계](./docs/chunker-implementation.md)

---

## Findings

> 구현 완료 후 작성

---

## Decision

> 구현 완료 후 작성
