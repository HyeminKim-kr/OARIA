# Spikes

이 디렉토리는 **새로운 아이디어·기술·아키텍처를 짧게 검증하기 위한 실험용 코드(spike)** 를 모아두는 곳입니다.  
여기 있는 코드는 **빠른 학습 & 검증용**이며, **바로 프로덕션에 사용하지 않습니다.**

---

## 스파이크의 목적

- 새로운 기술 스택/라이브러리 검토 (예: 벡터 DB, LLM, 워크플로 엔진 등)
- 아키텍처 아이디어 빠른 프로토타이핑
- 성능/비용/복잡도 등 “대략적인 감” 잡기
- 팀 내 공유용 데모/PoC 코드

스파이크에서 얻은 결론만 추려서  
**`backend/`, `frontend/`, `infra-terraform/` 등의 실제 서비스 코드에 반영**합니다.

---

## 디렉토리 네이밍 규칙

스파이크 폴더는 다음 규칙을 권장합니다.

```text
spikes/
  YYYY-MM-<간단주제>-spike/
```

예시:

```text
spikes/
  2025-01-vector-store-spike/
  2025-02-rag-chat-flow-spike/
  2025-03-bio-etl-pipeline-spike/
```

* `YYYY-MM` : 스파이크를 시작한 년/월
* `<간단주제>` : 한눈에 주제가 보이도록 짧게
* `-spike` : 실험 코드임을 명확히 표시

---

## 각 스파이크 폴더의 구조 예시

```text
spikes/
  2025-01-vector-store-spike/
    README.md        # 이 스파이크의 목적/결론 정리
    docker-compose.yml
    src/
      ...
    notes.md         # 실험 중 메모 (선택)
```

### 각 스파이크 `README.md`에 포함할 내용

* **Background**

  * 이 스파이크를 하게 된 이유, 관련 이슈/요구사항 링크
* **Goal**

  * 어떤 질문에 답을 얻고 싶은지 (예: “벡터 DB A vs B 성능 차이”)
* **How to Run**

  * 컨테이너 실행/종료 방법, 필요 환경변수 등
* **Findings**

  * 실험 결과 요약, 장단점, 숫자/로그 등
* **Decision**

  * ✅ 채택 / ❌ 보류 / ⏸︎ 재검토
  * 실제 서비스에 반영할 TODO (예: “backend 서비스에 A 라이브러리 도입”)

---

## 스파이크 라이프사이클

1. **생성**

   * 위 네이밍 규칙에 맞춰 폴더 생성
   * 최소한의 `README.md`와 실행 스크립트/compose 파일 작성
2. **실험 & 피드백**

   * 실험 후 팀/본인 피드백 정리
3. **결론 정리**

   * `README.md`의 **Findings / Decision** 섹션 업데이트
4. **프로덕션 반영**

   * 필요한 부분만 `backend/`, `frontend/`, `infra-terraform/`로 옮겨 구현
5. **정리**

   * 더 이상 안 쓰는 스파이크는 `ARCHIVED` 태그 추가 또는 하위 `archive/`로 이동(선택)

---

## 팀 스파이크 (동일 주제, 다중 구현)

여러 명이 같은 주제를 **각자 다르게 구현**하여 비교/검토할 때 사용합니다.

### 목적

- 같은 문제에 대한 다양한 접근 방식 탐색
- 팀원 간 상호 피드백 및 학습
- 최적의 구현 방식 선택

### 폴더 구조

**이니셜로 개인별 폴더 구분:**

```text
spikes/
  YYYY-MM-<주제>-spike/
    README.md              # 공통: 목표, 비교 결과, 최종 결론
    <이니셜>/              # 개인별 구현
      README.md            # 개인: 접근 방식, 결과
      src/
      output/
```

예시:

```text
spikes/
  2025-12-pubmed-api-spike/
    README.md
    tsy/
      README.md
      src/
        crawler.py
      output/
    kjh/
      README.md
      src/
        crawler.py
      output/
    plk/
      README.md
      src/
        crawler.py
      output/
```

### 브랜치 전략

각자 **자신의 이니셜이 포함된 브랜치**에서 작업:

```bash
# 브랜치 생성
git checkout dev
git checkout -b spike/pubmed-api-tsy

# 자기 폴더에서 작업
cd spikes/2025-12-pubmed-api-spike/tsy/

# 커밋 (Jira Sub-task 번호 포함)
git commit -m "OAR-50 requests 기반 PubMed API 구현"

# PR 생성 → dev로 머지
```

**장점:** 각자 다른 폴더에서 작업하므로 **3개 브랜치 모두 충돌 없이 머지 가능**

### 공통 README.md 작성 가이드

스파이크 완료 후 **비교 결과**를 공통 README.md에 정리:

```markdown
## Findings

| 구현 | 접근 방식 | 장점 | 단점 | 성능 |
|------|----------|------|------|------|
| tsy | requests (동기) | 단순함 | 느림 | 100건/분 |
| kjh | httpx (비동기) | 빠름, 깔끔 | 약간 복잡 | 300건/분 |
| plk | aiohttp | 가장 빠름 | 러닝커브 | 350건/분 |

## Decision

✅ **kjh 구현 채택** - 성능과 복잡도 밸런스 최적

### 이유
- 비동기 지원으로 충분한 성능
- httpx는 requests와 API가 유사하여 팀 적응 용이
- 타임아웃, 재시도 등 기본 제공

### 다음 단계
- [ ] backend/app/services/에 kjh 코드 기반으로 구현
- [ ] 테스트 코드 작성
- [ ] 에러 핸들링 강화
```

### Jira 연동

각 개인 구현은 **Jira Sub-task**로 관리:

```
Task: OAR-18 (PubMed API 연동)
├── Sub-task: OAR-50 (tsy 구현) → spike/pubmed-api-tsy
├── Sub-task: OAR-51 (kjh 구현) → spike/pubmed-api-kjh
└── Sub-task: OAR-52 (plk 구현) → spike/pubmed-api-plk
```

커밋 메시지에 Sub-task 번호를 포함하면 Jira에서 자동 추적됩니다.

---

## 스파이크 간 연결 (파이프라인 구성)

하나의 기능이 여러 단계로 나뉠 때 (예: 크롤링 → 임베딩 → 벡터DB), 각 스파이크를 **독립적으로 실험**하되 **나중에 연결 가능**하도록 구성합니다.

### 원칙

1. **input/output 포맷을 명확히 정의**
2. **각 스파이크는 파일로 입출력** (스파이크 단계)
3. **프로덕션 반영 시 함수 호출로 연결** (통합 단계)

### 폴더 구조 예시

```text
spikes/
  2025-12-crawling-spike/
    src/
      crawler.py
    output/
      papers.json           # 출력 결과물

  2025-12-embedding-spike/
    src/
      embedder.py
    output/
      embeddings.json

  2025-12-vectordb-spike/
    src/
      store.py
```

### 작업 흐름

**Step 1: 크롤링 스파이크**

```python
# src/crawler.py
import json

OUTPUT_PATH = "spikes/2025-12-crawling-spike/output/papers.json"

def crawl_papers(query: str, limit: int) -> list[dict]:
    # ... API 호출
    return papers

if __name__ == "__main__":
    papers = crawl_papers("lung cancer", limit=100)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"출력 경로: {OUTPUT_PATH}")
```

**Step 2: 임베딩 스파이크**

```python
# src/embedder.py
import json

# 이전 스파이크 출력 경로 직접 참조
INPUT_PATH = "spikes/2025-12-crawling-spike/output/papers.json"
OUTPUT_PATH = "spikes/2025-12-embedding-spike/output/embeddings.json"

def embed_papers(papers: list[dict]) -> list[dict]:
    # ... 임베딩 로직
    return embeddings

if __name__ == "__main__":
    with open(INPUT_PATH) as f:
        papers = json.load(f)
    embeddings = embed_papers(papers)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(embeddings, f, indent=2)

    print(f"출력 경로: {OUTPUT_PATH}")
```

**Step 3: 프로덕션 통합**

스파이크 검증 완료 후 `backend/`에 통합 시:

```python
# backend/app/services/paper_pipeline.py
from .crawler import crawl_papers
from .embedder import embed_papers
from .store import store_to_qdrant

def run_pipeline(query: str, limit: int):
    """파이프라인으로 연결"""
    papers = crawl_papers(query, limit)
    embeddings = embed_papers(papers)
    store_to_qdrant(embeddings)
    return {"processed": len(papers)}
```

### 핵심 포인트

| 단계 | 방식 | 이유 |
|------|------|------|
| 스파이크 | 파일로 입출력 | 독립 실험, 디버깅 용이 |
| 프로덕션 | 함수 호출로 연결 | 성능, 메모리 효율 |

### 데이터 포맷 합의

스파이크 시작 전 팀원 간 **output 포맷만 먼저 합의**하면 나중에 연결이 쉬워집니다.

```python
# 예: 크롤링 output 포맷
{
    "pmid": "12345678",
    "title": "...",
    "abstract": "...",
    "full_text": "..."  # nullable
}
```

---

## Python 환경 설정

스파이크에서 Python을 사용할 때는 **uv**를 사용합니다.

```bash
# 가상환경 생성 및 의존성 설치
uv sync

# 스크립트 실행
uv run python main.py

# 또는 FastAPI 등 서버 실행
uv run uvicorn app:app --reload
```

---

## 주의사항

* 이 디렉토리의 코드는 **실험용**이므로

  * 보안, 예외처리, 성능 등은 "필요 최소한"만 신경 씁니다.
  * 대신 **결론과 배운 점을 잘 남기는 것**이 더 중요합니다.
* 실제 제품 코드에 들어갈 때는 반드시

  * 코드 스타일, 테스트, 보안 가이드를 다시 적용합니다.

---

> **TL;DR**
> `spikes/`는 *"짧게 찔러보는 기술 실험 공간"* 입니다.
> 여기서 확인한 것만 정리해서, 진짜 구현은 본 서비스 디렉토리에서 진행하세요.