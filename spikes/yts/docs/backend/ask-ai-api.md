# Ask AI API 설계

> **작성일**: 2026-01-01
>
> **상태**: Draft (UI 구현 후 세부 확정)

---

## TL;DR

| 항목 | 내용 |
|------|------|
| **엔드포인트** | `POST /ai/ask` |
| **기능** | RAG 기반 질의응답 + 관련 논문 반환 |
| **응답 방식** | SSE 스트리밍 |

> **Note**: 프롬프트 템플릿, Ask 용도 정의, 검색 전략 세부사항은 UI 구현 후 논의 예정

---

## 1. 페이지 구조 (UI)

### 1.1 레이아웃 옵션

| 옵션 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **A. 반반 구조** | 좌: 채팅, 우: 참고문헌 | 한눈에 보임 | 모바일 대응 어려움 |
| **B. 탭 전환** | 답변 / 참고문헌 탭 | 모바일 친화적 | 전환 필요 |
| **C. 접히는 패널** | 참고문헌 접기/펼치기 | 유연함 | UX 복잡 |
| **D. 답변 하단 배치** | 답변 아래 참고문헌 리스트 | 단순함 | 스크롤 길어짐 |

### 1.2 권장: D. 답변 하단 배치 (또는 B. 탭 전환)

```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Home              Ask AI                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 👤 폐암 면역치료 최신 연구 동향 알려줘               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🤖 최근 폐암 면역치료 연구는 크게 3가지 방향으로...  │   │
│  │                                                     │   │
│  │ 1. **PD-L1 발현** - 면역관문억제제 반응 예측 [1]    │   │
│  │ 2. **CAR-T 세포치료** - 고형암 적용 연구 [2]       │   │
│  │ 3. **병용요법** - 화학요법+면역치료 조합 [3]        │   │
│  │                                                     │   │
│  │ ─────────────────────────────────────────────────── │   │
│  │ 📚 References                                       │   │
│  │ [1] Immunotherapy Response... (Nature, 2025)       │   │
│  │ [2] CAR-T Cell Therapy... (Cancer Cell, 2025)      │   │
│  │ [3] Combination Therapy... (JAMA Oncology, 2024)   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💬 Ask about research...                    [Send]  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. API 설계 (초안)

### 2.1 Ask AI

```
POST /ai/ask
Content-Type: application/json
Accept: text/event-stream
```

**Request:**
```json
{
  "question": "폐암 면역치료 최신 연구 동향 알려줘",
  "conversation_id": "uuid (optional)",
  "filters": {
    "year_from": 2020,
    "sections": ["results", "discussion"]
  }
}
```

**Response (SSE):**
```
event: references
data: {"references": [{"paper_id": "...", "title": "...", "section": "..."}]}

event: token
data: {"token": "최근"}

event: token
data: {"token": " 폐암"}

...

event: done
data: {"conversation_id": "uuid"}
```

### 2.2 응답 구조

```typescript
interface AskResponse {
  // 스트리밍으로 전달
  answer: string;

  // 먼저 전달 (references 이벤트)
  references: Reference[];
}

interface Reference {
  paper_id: string;
  pmcid: string;
  title: string;
  journal: string;
  year: number;
  section: string;      // 사용된 섹션
  relevance_score: number;
}
```

---

## 3. 추후 논의 필요 사항

### 3.1 Ask의 용도 정의

| 옵션 | 설명 |
|------|------|
| A. 논문 검색 도우미 | "~에 관한 논문 찾아줘" → 논문 리스트 |
| B. 연구 질의응답 | "~가 뭐야?" → AI 답변 + 근거 논문 |
| C. 혼합 | 의도 파악 → 적절한 응답 |

### 3.2 프롬프트 템플릿

- System prompt 설계
- 인용 형식 지정
- 답변 톤/길이 조절
- 불확실성 표현 방식

### 3.3 고급 기능

- 대화 히스토리 (follow-up 질문)
- 저자별 논문 검색
- 특정 논문 기반 질문

---

## 4. 구현 우선순위

### Phase 1: UI 먼저
- [ ] Ask AI 페이지 라우팅
- [ ] 채팅 인터페이스 (입력/출력)
- [ ] 참고문헌 표시 영역

### Phase 2: Backend 연동
- [ ] API 엔드포인트 구현
- [ ] SSE 스트리밍
- [ ] RAG 파이프라인 연결

### Phase 3: 세부 기능
- [ ] 프롬프트 템플릿 확정
- [ ] 필터링 옵션
- [ ] 대화 히스토리

---

## 참고

- [retrieval-strategy.md](./retrieval-strategy.md) - 검색 전략
- [paper-search-flow.md](./paper-search-flow.md) - 논문 검색 API
