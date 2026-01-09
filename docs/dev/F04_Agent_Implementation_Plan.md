# F-04 Agent Task Decomposition Implementation Plan

> **Owner**: 김혜민
> **Jira Epic**: OAR-14
> **Sub-tickets**: OAR-46 ~ OAR-51
> **Created**: 2026-01-07
> **Status**: ✅ **COMPLETED** (2026-01-08)

## Overview

Add LangGraph-based agent system to the existing OARIA backend for complex query decomposition and multi-step execution.

**Goal**: Complex queries like "EGFR+TP53 이중 변이 환자의 1차 치료 vs 2차 치료 효과 비교" get decomposed into sub-tasks, executed (parallel/sequential), and synthesized into a final answer.

---

## ✅ Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| OAR-46: LangGraph Setup | ✅ Done | State, Graph, Service singleton |
| OAR-47: Complexity Analyzer | ✅ Done | Simple/Medium/Complex classification |
| OAR-48: Task Decomposer | ✅ Done | 2-5 tasks with deduplication |
| OAR-49: Tool Router | ✅ Done | rag_search, compare, summarize |
| OAR-50: Executor | ✅ Done | Parallel execution, direct_rag for simple |
| OAR-51: Synthesizer | ✅ Done | Evidence synthesis with citations |
| API Endpoint | ✅ Done | `/ai/ask-agent` with SSE streaming |
| Frontend Integration | ✅ Done | Task progress UI with status icons |
| Unit Tests | ✅ Done | 13 tests passing |
| Integration Tests | ✅ Done | Real services tested |

### Key Implementation Decisions

1. **Task Structure (Enforced)**:
   - First 2-3 tasks: `rag_search` (parallel)
   - Second-to-last: `compare` (depends on rag_search)
   - Last task: `summarize` (depends on all previous)

2. **Deduplication**:
   - Prompts explicitly forbid duplicate tasks
   - Code checks for >80% word overlap between queries
   - Max 5 tasks enforced

3. **Performance Optimizations**:
   - Reranker uses MPS (Apple Silicon) / CUDA GPU acceleration
   - FP16 half-precision inference (~2-3s per rerank instead of 5-7s)
   - Streaming tokens during synthesis for responsive UI

---

## Architecture Integration

```
                          ┌─────────────────────────────────────┐
                          │         NEW: AgentService           │
                          │  ┌─────────────────────────────┐    │
User Query ──────────────►│  │   Complexity Analyzer       │    │
                          │  │   (Simple/Medium/Complex)   │    │
                          │  └──────────┬──────────────────┘    │
                          │             │                        │
                          │   Simple ◄──┼──► Medium/Complex      │
                          │      │      │         │              │
                          │      ▼      │         ▼              │
                          │  ┌──────┐   │   ┌───────────────┐   │
                          │  │ RAG  │   │   │Task Decomposer│   │
                          │  │Direct│   │   └───────┬───────┘   │
                          │  └──┬───┘   │           │           │
                          │     │       │           ▼           │
                          │     │       │   ┌───────────────┐   │
                          │     │       │   │ Tool Router   │   │
                          │     │       │   └───────┬───────┘   │
                          │     │       │           │           │
                          │     │       │           ▼           │
                          │     │       │   ┌───────────────┐   │
                          │     │       │   │   Executor    │───┼──► rag_service
                          │     │       │   │ (parallel/seq)│───┼──► llm_service
                          │     │       │   └───────┬───────┘   │
                          │     │       │           │           │
                          │     │       │           ▼           │
                          │     │       │   ┌───────────────┐   │
                          │     └───────┼──►│  Synthesizer  │   │
                          │             │   └───────┬───────┘   │
                          └─────────────┼───────────┼───────────┘
                                        │           │
                                        ▼           ▼
                                   Final Answer + Citations
```

---

## Implementation Tasks (OAR-46 to OAR-51)

### OAR-46: LangGraph Project Setup
**Files to create/modify:**
- `backend/pyproject.toml` - Add langgraph dependency
- `backend/app/services/agent/` - New agent module directory
- `backend/app/services/agent/__init__.py`
- `backend/app/services/agent/state.py` - AgentState TypedDict
- `backend/app/services/agent/graph.py` - Graph builder

**State Schema:**
```python
class AgentState(TypedDict):
    query: str                          # Original user query
    complexity: str                     # simple/medium/complex
    subtasks: list[SubTask]             # Decomposed tasks
    execution_plan: list[str]           # Order of execution
    task_results: dict[str, TaskResult] # Results per task
    final_answer: str                   # Synthesized answer
    citations: list[Reference]          # All citations
    error: str | None                   # Error message if failed
```

---

### OAR-47: Complexity Analyzer Node
**File:** `backend/app/services/agent/nodes/complexity_analyzer.py`

**Logic:**
- Use LLM (GPT-4o-mini) to classify query complexity
- Prompt includes examples for each level
- Returns: `{"complexity": "simple" | "medium" | "complex", "reasoning": str}`

**Routing:**
- Simple → Direct RAG (existing rag_service.retrieve + llm_service.generate)
- Medium/Complex → Task Decomposer

---

### OAR-48: Task Decomposer Node
**File:** `backend/app/services/agent/nodes/task_decomposer.py`

**Logic:**
- LLM decomposes query into 2-5 sub-tasks
- Each sub-task has: query, reasoning, tool_hint, dependencies
- Identifies parallel vs sequential execution

**Output:**
```python
@dataclass
class SubTask:
    id: str                    # "task_1", "task_2"
    query: str                 # Sub-query to execute
    reasoning: str             # Why this sub-task
    tool_hint: str             # "rag" | "compare" | "synthesize"
    depends_on: list[str]      # Task IDs this depends on
```

---

### OAR-49: Tool Router Node
**File:** `backend/app/services/agent/nodes/tool_router.py`

**Available Tools:**
1. `rag_search` - Uses existing `rag_service.retrieve()`
2. `compare` - LLM comparison of two concepts
3. `summarize` - LLM summarization of results

**Logic:**
- Maps each sub-task to appropriate tool
- Identifies parallelizable tasks (no dependencies)

---

### OAR-50: Executor Node
**File:** `backend/app/services/agent/nodes/executor.py`

**Logic:**
- Execute tasks respecting dependency order
- Parallel execution for independent tasks using `asyncio.gather()`
- Collect results and citations per task
- Retry logic for transient failures (max 2 retries)

**Tool Implementations:**
```python
async def execute_rag(subtask: SubTask) -> TaskResult:
    result = await asyncio.to_thread(rag_service.retrieve, subtask.query)
    return TaskResult(
        task_id=subtask.id,
        content=result.context,
        references=result.references,
    )

async def execute_compare(subtask: SubTask, context: dict) -> TaskResult:
    # LLM comparison using previous task results
    ...
```

---

### OAR-51: Evidence Synthesizer Node
**File:** `backend/app/services/agent/nodes/synthesizer.py`

**Logic:**
- Combine all task results
- LLM generates final answer with citations
- Merge and deduplicate citations from all tasks
- Format answer in same style as existing `/ai/ask` endpoint

---

## New Files Structure

```
backend/app/
├── services/
│   ├── agent/
│   │   ├── __init__.py           # Export agent_service
│   │   ├── service.py            # AgentService singleton
│   │   ├── state.py              # AgentState TypedDict
│   │   ├── graph.py              # LangGraph graph builder
│   │   ├── prompts.py            # All LLM prompts
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── complexity_analyzer.py
│   │       ├── task_decomposer.py
│   │       ├── tool_router.py
│   │       ├── executor.py
│   │       └── synthesizer.py
│   └── __init__.py               # Add agent_service export
├── schemas/
│   └── agent.py                  # Agent request/response schemas
├── routers/
│   └── ai.py                     # Add /ai/ask-agent endpoint
└── models/
    └── agent_log.py              # Optional: AgentExecutionLog model
```

---

## API Endpoint Design

### SSE Streaming Endpoint
```
POST /ai/ask-agent
Request: { question, conversation_id?, filters? }

SSE Events:
1. {"event": "status", "data": {"step": "analyzing", "message": "쿼리 복잡도 분석 중..."}}
2. {"event": "complexity", "data": {"level": "complex", "reasoning": "..."}}
3. {"event": "subtasks", "data": {"tasks": [...]}}
4. {"event": "task_start", "data": {"task_id": "task_1", "query": "..."}}
5. {"event": "task_complete", "data": {"task_id": "task_1", "summary": "..."}}
   ... (repeat for each task)
6. {"event": "synthesizing", "data": {"message": "결과 종합 중..."}}
7. {"event": "token", "data": {"token": "..."}}  // Stream final answer
8. {"event": "references", "data": {"references": [...]}}
9. {"event": "done", "data": {"conversation_id": "...", "message_id": "..."}}
```

### Fallback for Simple Queries
If complexity = "simple", redirect to existing RAG pipeline (same as `/ai/ask`).

---

## Integration Points

### Use Existing Services
- `rag_service.retrieve()` - For sub-task RAG searches
- `llm_service.generate_stream()` - For final answer streaming
- `embedding_service` - Query embeddings (if needed)
- `weaviate_service` - Direct vector search (if needed)

### Database Integration
- Reuse `Conversation`, `Message`, `AnswerLog` models
- Store agent execution in `AnswerLog.evidence` (extended schema)

---

## Dependencies to Add

```toml
# backend/pyproject.toml
dependencies = [
    # ... existing ...
    "langgraph>=0.2.0",
]
```

---

## Success Criteria Mapping

| Jira AC | Implementation |
|---------|----------------|
| AC-1: 복잡도 분류 ≥90% | Complexity Analyzer with few-shot examples |
| AC-2: Task 분해 ≥85% | Task Decomposer with structured output |
| AC-3: Complex 처리 <15s | Parallel execution + streaming |
| AC-4: RAGAS ≥0.80 | Synthesizer with citation requirements |

---

## Implementation Order

1. **OAR-46**: Setup LangGraph, create state and basic graph structure
2. **OAR-47**: Complexity Analyzer (enables routing)
3. **OAR-48**: Task Decomposer (core logic)
4. **OAR-49**: Tool Router (simple mapping)
5. **OAR-50**: Executor (integration with existing services)
6. **OAR-51**: Synthesizer (final output)
7. **API Endpoint**: Add `/ai/ask-agent` with SSE streaming
8. **Testing**: Unit tests + integration tests

---

## Key Files to Modify

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add langgraph dependency |
| `backend/app/services/__init__.py` | Export agent_service |
| `backend/app/routers/ai.py` | Add /ai/ask-agent endpoint |
| `backend/app/schemas/__init__.py` | Export agent schemas |

---

## Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Style | **SSE Streaming** | Real-time progress updates, consistent with existing `/ai/ask` |
| Logging | **Extend AnswerLog** | No migration needed, reuse existing schema |
| Frontend | **Show progress** | User will update frontend to display sub-task progress |

---

## AnswerLog.evidence Extended Schema

```python
# Existing evidence structure (list of references)
# Extended to include agent execution data

evidence = {
    "references": [...],           # Existing: list of Reference
    "agent_execution": {           # NEW: agent-specific data
        "complexity": "complex",
        "complexity_reasoning": "...",
        "subtasks": [
            {
                "id": "task_1",
                "query": "EGFR 변이 특성",
                "tool": "rag_search",
                "status": "completed",
                "duration_ms": 1200,
                "references_count": 3
            },
            ...
        ],
        "total_subtasks": 4,
        "parallel_tasks": 2,
        "total_duration_ms": 5400
    }
}
```

---

## Frontend SSE Event Handling

The frontend should handle these events for progress display:

```typescript
// Event types for agent endpoint
type AgentEvent =
  | { event: "status"; data: { step: string; message: string } }
  | { event: "complexity"; data: { level: string; reasoning: string } }
  | { event: "subtasks"; data: { tasks: SubTask[] } }
  | { event: "task_start"; data: { task_id: string; query: string } }
  | { event: "task_complete"; data: { task_id: string; summary: string } }
  | { event: "synthesizing"; data: { message: string } }
  | { event: "token"; data: { token: string } }
  | { event: "references"; data: { references: Reference[] } }
  | { event: "done"; data: { conversation_id: string; message_id: string } };
```
