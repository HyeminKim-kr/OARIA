# Study Plan Agent - Frontend Architecture

> **작성일**: 2025-01-30
> **백엔드 문서**: `backend/app/services/agent/study_plan/README.md`

이 문서는 Study Plan Agent의 프론트엔드 아키텍처를 설명합니다.

---

## 목차

1. [디렉토리 구조](#디렉토리-구조)
2. [데이터 흐름](#데이터-흐름)
3. [주요 컴포넌트](#주요-컴포넌트)
4. [SSE 이벤트 처리](#sse-이벤트-처리)
5. [타입 정의](#타입-정의)
6. [수정 시 주의사항](#수정-시-주의사항)

---

## 디렉토리 구조

```
study-plan/
├── page.tsx                    # 메인 페이지 (상태 관리의 핵심)
├── layout.tsx                  # 레이아웃
├── types.ts                    # 타입 정의 ⭐
├── constants.tsx               # 상수 (레거시)
│
├── constants/                  # 이벤트 상수
│   ├── events.ts               # AgentEventType ⭐ 백엔드와 동기화 필수
│   └── index.ts
│
├── components/                 # UI 컴포넌트들
│   ├── index.ts                # 컴포넌트 export
│   │
│   │ # 핵심 컴포넌트
│   ├── ExtendedThinkingPanel.tsx   # 사고 과정 패널 ⭐
│   ├── ObservationDetailsCard.tsx  # 관찰 결과 카드 ⭐
│   ├── ResultsPanel.tsx            # 최종 결과 패널 ⭐
│   ├── SourcesCard.tsx             # 출처 카드 (Perplexity 스타일)
│   │
│   │ # 입력/폼 컴포넌트
│   ├── HypothesisForm.tsx      # 가설 입력 폼
│   ├── RecoverySelector.tsx    # 복구 옵션 선택
│   │
│   │ # 시각화 컴포넌트
│   ├── CollapsibleTree.tsx     # 트리 구조 표시
│   ├── LiveActivityFeed.tsx    # 실시간 활동 피드
│   ├── TimelinePlayer.tsx      # 타임라인 재생
│   ├── TokenTracker.tsx        # 토큰 사용량 추적
│   │
│   │ # 기타
│   ├── ExportButton.tsx        # 내보내기 버튼
│   ├── LandingSection.tsx      # 랜딩 섹션
│   └── NodeDetailModal.tsx     # 노드 상세 모달
│
├── utils/                      # 유틸리티
│   ├── exportUtils.ts          # 내보내기 유틸
│   └── sessionStorage.ts       # 세션 저장
│
└── history/                    # 히스토리 페이지
    └── page.tsx
```

---

## 데이터 흐름

### 전체 흐름

```
┌─────────────────────────────────────────────────────────────────────┐
│ Backend SSE Stream                                                  │
│   → event: thinking/acting/observation/completed/result             │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ useJobStream Hook (src/hooks/useJobStream.ts)                       │
│   → SSE 연결 관리                                                    │
│   → 이벤트 파싱                                                      │
│   → 콜백 호출 (onEvent, onCompleted, etc.)                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ page.tsx (메인 페이지)                                               │
│   → thinkingSteps 상태 관리                                          │
│   → resultData 상태 관리                                             │
│   → 이벤트별 처리 로직                                               │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Components                                                          │
│   ├── ExtendedThinkingPanel → 사고 과정 표시                         │
│   ├── ObservationDetailsCard → 각 액션 결과 상세                     │
│   └── ResultsPanel → 최종 결과 (Plan A/B, 근거 자료 등)              │
└─────────────────────────────────────────────────────────────────────┘
```

### page.tsx 핵심 상태

```typescript
// 사고 과정 스텝들
const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);

// 최종 결과 데이터
const [resultData, setResultData] = useState<{
  finalPlan?: string;
  executiveSummary?: string;
  planA?: string;
  planB?: string;
  experimentCount?: number;
  totalDuration?: number;
  paperCount?: number;
  snippetCount?: number;
  // ⭐ 핵심: 검색된 논문/스니펫 실제 데이터
  retrievedPapers?: RetrievedPaper[];
  evidenceSnippets?: EvidenceSnippet[];
}>({});
```

---

## 주요 컴포넌트

### 1. ExtendedThinkingPanel

**위치**: `components/ExtendedThinkingPanel.tsx`

사고 과정을 표시하는 메인 패널. Claude의 Extended Thinking 스타일.

```tsx
<ExtendedThinkingPanel
  steps={thinkingSteps}
  isLoading={status === "running"}
  maxHeight="600px"
/>
```

**표시하는 이벤트**:
- `thinking` - LLM 사고 과정
- `acting` - 액션 실행 중
- `observation` - 액션 결과 (sources 카드 포함)
- `goal_check` - 목표 달성 검사

### 2. ObservationDetailsCard

**위치**: `components/ObservationDetailsCard.tsx`

각 observation 이벤트의 상세 정보를 표시.

```tsx
// ExtendedThinkingPanel 내부에서 사용
<ObservationDetailsCard
  details={step.observationDetails}
  action={step.action}
/>
```

**검색 결과 표시 시**:
```tsx
// searchType prop으로 검색 소스 구분
<SearchDetails
  papers={details.papers}
  totalCount={details.total_count}
  coverage={details.coverage}
  searchType={details.type}  // "search_rag" | "search_epmc" | "search_web"
/>
```

**소스 뱃지 스타일**:
| 소스 | 라벨 | 색상 |
|------|------|------|
| `search_rag` | RAG | 에메랄드 (emerald) |
| `search_epmc` | EPMC | 블루 (blue) |
| `search_web` | External Research | 오렌지 (orange) |

### 3. SourcesCard ⭐

**위치**: `components/SourcesCard.tsx`

Perplexity 스타일의 출처 카드. 검색 결과를 클릭 가능한 카드로 표시.

```tsx
<SourcesCard
  sources={step.sources}
  summary={step.summary}
  action={step.action}
  isLoading={false}
/>
```

**클릭 동작**:
- Paper 타입: URL이 있으면 새 탭에서 열기, 없으면 상세 정보 토글
- Web 타입: 바로 새 탭에서 URL 열기

**URL Fallback 로직** (`getPaperUrl` 함수):
```typescript
const getPaperUrl = (source: PaperSource): string | null => {
  // 우선순위: url > DOI > PMC > PubMed
  if (source.url) return source.url;
  if (source.doi) return `https://doi.org/${source.doi}`;
  if (source.pmcid) return `https://europepmc.org/article/PMC/${source.pmcid}`;
  if (source.pmid) return `https://pubmed.ncbi.nlm.nih.gov/${source.pmid}/`;
  return null;
};
```

**클릭 핸들러**:
```typescript
const handlePaperClick = (source: PaperSource) => {
  const url = getPaperUrl(source);
  if (url) {
    window.open(url, "_blank", "noopener,noreferrer");
  } else {
    // URL 없으면 상세 정보 토글
    setSelectedSource(selectedSource === source.id ? null : source.id);
  }
};
```

**Source 타입별 표시**:
| 타입 | 아이콘 | 동작 |
|------|--------|------|
| `paper` | BookOpen / ExternalLink | URL 있으면 클릭으로 이동 |
| `snippet` | Quote | 인용문 표시만 |
| `web` | Globe | 바로 새 탭에서 열기 |

### 4. ResultsPanel

**위치**: `components/ResultsPanel.tsx`

최종 결과를 탭으로 구분하여 표시.

```tsx
<ResultsPanel
  finalPlan={resultData.finalPlan}
  executiveSummary={resultData.executiveSummary}
  planA={resultData.planA}
  planB={resultData.planB}
  experimentCount={resultData.experimentCount}
  totalDuration={resultData.totalDuration}
  paperCount={resultData.paperCount}
  snippetCount={resultData.snippetCount}
  retrievedPapers={resultData.retrievedPapers}    // ⭐ 논문 목록
  evidenceSnippets={resultData.evidenceSnippets}  // ⭐ 스니펫 목록
/>
```

**탭 구성**:
| 탭 | 설명 |
|----|------|
| 요약 | Executive Summary, Plan A/B 토글 |
| 실험 설계 | 설계된 실험 목록 |
| **근거 자료** | 논문/스니펫 목록 ⭐ (클릭 가능) |
| 전체 계획서 | 마크다운 렌더링 |

**논문 클릭 처리** (`ResultsPanel.tsx:455`):
```typescript
// URL fallback 로직
const paperUrl = paper.url
  || (paper.doi ? `https://doi.org/${paper.doi}` : null)
  || (paper.pmcid ? `https://europepmc.org/article/PMC/${paper.pmcid}` : null)
  || (paper.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/` : null)
  || extractUrlFromMarkdown(paper.markdown_link);

// 클릭 핸들러
const handleClick = () => {
  if (paperUrl) {
    window.open(paperUrl, "_blank", "noopener,noreferrer");
  }
};
```

---

## SSE 이벤트 처리

### 이벤트 타입 (`constants/events.ts`)

```typescript
export const AgentEventType = {
  // Lifecycle
  INITIALIZATION: "initialization",
  STARTED: "started",
  COMPLETED: "completed",
  ERROR: "error",

  // Reasoning/Action
  THINKING: "thinking",
  REASONING: "reasoning",
  ACTING: "acting",
  OBSERVATION: "observation",  // ⭐ 검색 결과 포함

  // Goal/Recovery
  GOAL_CHECK: "goal_check",
  RECOVERY: "recovery",
  USER_INPUT_REQUEST: "user_input_request",

  // Result
  RESULT: "result",
} as const;
```

### page.tsx에서 이벤트 처리

```typescript
// observation 이벤트 처리 예시
case "observation":
  const newStep: ThinkingStep = {
    id: `obs-${Date.now()}`,
    type: "observation",
    timestamp: new Date(),
    iteration: eventData.iteration,
    action: eventData.action,
    success: eventData.success,
    duration_ms: eventData.duration_ms,
    // ⭐ sources 배열 (Perplexity 스타일 카드용)
    sources: eventData.sources,
    summary: eventData.summary,
    // ⭐ 상세 정보 (ObservationDetailsCard용)
    observationDetails: eventData.details,
  };
  setThinkingSteps(prev => [...prev, newStep]);
  break;
```

### observation 이벤트의 sources 구조

```typescript
// 백엔드 execute.py의 _extract_sources()에서 생성
sources: [
  {
    id: 1,
    type: "paper",
    title: "논문 제목...",
    url: "https://doi.org/...",       // ⭐ 클릭 가능
    source: "rag",                     // ⭐ 검색 소스
    doi: "10.1234/...",
    pmid: "12345678",
    pmcid: "PMC1234567",
    journal: "Nature",
    year: 2024,
    relevance: 0.85,
    citation_text: "논문 제목...",
    markdown_link: "[논문 제목](https://...)",
  }
]
```

---

## 타입 정의

### 통합 논문 타입 (`types.ts` 및 `ResultsPanel.tsx`)

```typescript
interface RetrievedPaper {
  // 공통 필수 필드
  title: string;
  url?: string;
  score?: number;
  source?: "rag" | "epmc" | "web";  // ⭐ 검색 소스
  citation_text?: string;
  markdown_link?: string;

  // 논문 전용 필드
  paper_id?: string;
  journal?: string;
  year?: number;
  doi?: string;
  pmcid?: string;
  pmid?: string;

  // Web 전용 필드
  content?: string;
}
```

### Source 타입 (`types.ts`)

```typescript
export type Source = PaperSource | SnippetSource | WebSource;

export interface PaperSource {
  id: number;
  type: "paper";
  title: string;
  url?: string;           // ⭐ 논문 URL (클릭 시 이동)
  source?: string;        // ⭐ 검색 소스 (rag/epmc/web)
  journal?: string;
  year?: number;
  authors?: string[];
  relevance?: number;
  pmid?: string;
  pmcid?: string;         // ⭐ PMC ID
  doi?: string;
}

export interface SnippetSource {
  id: number;
  type: "snippet";
  text: string;
  section?: string;
  paper_id?: string;
  relevance?: number;
}

export interface WebSource {
  id: number;
  type: "web";
  title: string;
  url: string;            // ⭐ URL 필수
  description?: string;
}
```

**source 필드 값과 검색 도구 매핑**:
| source 값 | 백엔드 검색 도구 | 설명 |
|-----------|-----------------|------|
| `"rag"` | `search_rag` | Weaviate (내부 DB) |
| `"epmc"` | `search_epmc` | Europe PMC |
| `"web"` | `search_web` | Tavily 웹 검색 |

---

## 수정 시 주의사항

### 1. 백엔드 이벤트 필드 추가 시

백엔드에서 SSE 이벤트에 새 필드를 추가할 때:

1. **타입 업데이트** (`types.ts`)
   ```typescript
   // StudyPlanSSEEvent 또는 관련 인터페이스에 필드 추가
   export interface StudyPlanSSEEvent {
     // ...기존 필드
     newField?: string;  // ← 새 필드
   }
   ```

2. **Source 타입 업데이트** (필요 시)
   ```typescript
   export interface PaperSource {
     // ...
     newField?: string;
   }
   ```

3. **page.tsx 이벤트 처리 업데이트**
   ```typescript
   case "observation":
     const newStep = {
       // ...
       newField: eventData.newField,
     };
   ```

4. **컴포넌트 업데이트**
   - `ObservationDetailsCard.tsx`
   - `SourcesCard.tsx`
   - `ResultsPanel.tsx`

### 2. 검색 소스 뱃지 추가 시

새 검색 소스를 추가할 때:

1. **ObservationDetailsCard.tsx** (`SearchDetails` 컴포넌트)
   ```typescript
   const getSourceInfo = (type?: string) => {
     switch (type) {
       case "search_rag":
         return { label: "RAG", color: "..." };
       case "search_new_source":  // ← 추가
         return { label: "New", color: "..." };
       // ...
     }
   };
   ```

2. **ResultsPanel.tsx** (`getSourceBadge` 함수)
   ```typescript
   const getSourceBadge = (source?: string) => {
     switch (source) {
       case "rag":
         return { label: "RAG", className: "..." };
       case "new_source":  // ← 추가
         return { label: "New", className: "..." };
       // ...
     }
   };
   ```

### 3. 이벤트 타입 추가 시

1. **constants/events.ts** 업데이트
   ```typescript
   export const AgentEventType = {
     // ...
     NEW_EVENT: "new_event",  // ← 추가
   } as const;
   ```

2. **백엔드와 동기화 확인**
   - `backend/app/services/agent/study_plan/v4/constants/events.py`

### 4. URL 클릭이 안 될 때 체크리스트

1. **백엔드 확인**
   - `execute.py`의 `_extract_sources()` 함수에서 `url` 필드 포함 여부
   - `rag_tool.py`에서 Weaviate/Tavily 결과 분리 처리 확인
   - 검색 도구에서 `url` 필드 반환 여부

2. **프론트엔드 확인**
   - `SourcesCard.tsx`의 `getPaperUrl()` fallback 로직
   - `ResultsPanel.tsx`의 URL fallback 로직
   - `paperUrl` 값 console.log로 확인
   - `handlePaperClick` / `handleClick` 함수 호출 여부

3. **데이터 흐름 확인**
   ```
   검색 도구 (rag_tool.py)
     → papers[].url 필드 설정
     → execute.py (_extract_sources)
     → SSE event.sources[]
     → SourcesCard / ResultsPanel
   ```

---

## 관련 문서

- **백엔드 문서**: `backend/app/services/agent/study_plan/README.md`
- **프로젝트 규칙**: `CLAUDE.md`
- **useJobStream Hook**: `src/hooks/useJobStream.ts`

---

## 디버깅 팁

### 개발 환경 로그

`useJobStream.ts`는 개발 환경에서만 로그 출력:
```typescript
const isDev = process.env.NODE_ENV === "development";
const log = (...args: unknown[]) => isDev && console.log(...args);
```

### SSE 이벤트 확인

```typescript
// page.tsx에서 이벤트 로그
const handleEvent = (event: JobStreamEvent) => {
  console.log("[SSE Event]", event.event, event);
  // ...
};
```

### 논문 클릭 디버깅

```typescript
// ResultsPanel.tsx
const handleClick = () => {
  console.log("[Paper Click] paperUrl:", paperUrl);
  console.log("[Paper Click] paper data:", paper);
  if (paperUrl) {
    window.open(paperUrl, "_blank", "noopener,noreferrer");
  }
};
```
