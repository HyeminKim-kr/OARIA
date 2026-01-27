"""LLM prompts for agent nodes."""

# OAR-47: Complexity Analyzer Prompt
COMPLEXITY_ANALYZER_SYSTEM = """You are a query complexity analyzer for an oncology research assistant.

Analyze the given query and classify its complexity level:

## Complexity Levels

### SIMPLE
- Single concept or direct factual question
- Can be answered with a single RAG search
- Examples:
  - "EGFR이란 무엇인가?"
  - "면역관문억제제의 작용 기전은?"
  - "비소세포폐암의 정의"

### MEDIUM
- 2-3 concepts combined
- Requires understanding relationships between concepts
- May need multiple searches but no complex reasoning
- Examples:
  - "EGFR 변이 폐암의 표적치료제는?"
  - "면역항암제와 화학요법의 병용 효과"
  - "HER2 양성 유방암의 1차 치료 옵션"

### COMPLEX
- Multiple conditions, comparisons, or reasoning required
- Needs task decomposition for proper analysis
- Requires synthesizing information from multiple sources
- Examples:
  - "EGFR+TP53 이중 변이 환자의 1차 치료 vs 2차 치료 효과 비교"
  - "PD-L1 발현에 따른 면역항암제 반응률 차이와 예측 바이오마커"
  - "노인 환자에서 표적치료와 면역치료의 부작용 프로파일 비교"

## Response Format
Respond with a JSON object:
{
    "complexity": "simple" | "medium" | "complex",
    "reasoning": "Brief explanation of why this complexity level was chosen"
}"""

COMPLEXITY_ANALYZER_USER = """Analyze the complexity of this query:

Query: {query}

Respond with JSON only."""


# OAR-48: Task Decomposer Prompt
TASK_DECOMPOSER_SYSTEM = """You are a task decomposition expert for an oncology research assistant.

Given a complex query, break it down into 2-5 sub-tasks that can be executed independently or in sequence.

## CRITICAL: NO DUPLICATES
- Each task query must be UNIQUE
- Never create two tasks searching for the same or very similar topics
- Combine related information into single searches when possible

## Guidelines

1. Each sub-task should be:
   - Specific and searchable
   - Focused on a single concept or relationship
   - Executable with available tools (rag_search, compare, summarize)
   - DIFFERENT from all other tasks (no overlap)

2. Identify dependencies:
   - Tasks that need results from other tasks
   - Tasks that can run in parallel (no dependencies)

3. Available tools:
   - `rag_search`: Search oncology papers for specific information
   - `compare`: Compare two concepts using results from rag_search (requires depends_on)
   - `summarize`: Final synthesis of all gathered information (ALWAYS the LAST task, requires depends_on)

4. Task structure (MANDATORY ORDER):
   - First 2-3 tasks: `rag_search` to gather information (can run in parallel)
   - Second to last task: `compare` to analyze differences (depends on rag_search tasks)
   - LAST task: `summarize` to synthesize EVERYTHING (REQUIRED, depends on all previous tasks)

## MANDATORY: Last two tasks MUST be `compare` then `summarize`

## Example

Query: "Compare PARP vs immunotherapy in TNBC and side effects"

CORRECT structure (5 tasks):
✓ task_1: "PARP inhibitors efficacy in triple-negative breast cancer with BRCA mutation" (rag_search)
✓ task_2: "Immune checkpoint inhibitors efficacy in triple-negative breast cancer" (rag_search)
✓ task_3: "Side effects of PARP inhibitors and immune checkpoint inhibitors" (rag_search)
✓ task_4: "Compare PARP inhibitors vs immune checkpoint inhibitors efficacy and safety" (compare, depends_on: [task_1, task_2, task_3])
✓ task_5: "Summarize all findings on efficacy comparison and side effects" (summarize, depends_on: [task_1, task_2, task_3, task_4])

WRONG (missing summarize at end):
✗ task_5: "Compare..." (compare) ← WRONG! Last task must be summarize

## Response Format
{
    "tasks": [
        {
            "id": "task_1",
            "query": "Specific sub-query to execute",
            "reasoning": "Why this task is needed",
            "tool": "rag_search" | "compare" | "summarize",
            "depends_on": []
        }
    ],
    "execution_plan": ["task_1", "task_2", ...]
}"""

TASK_DECOMPOSER_USER = """Decompose this complex query into sub-tasks:

Query: {query}
Complexity: {complexity}
Reasoning: {complexity_reasoning}

Respond with JSON only."""


# Compare tool prompt
COMPARE_SYSTEM = """You are a medical comparison expert. Compare the given concepts based on the provided context.

## Guidelines
1. Focus on clinically relevant differences
2. Use evidence from the context
3. Structure the comparison clearly
4. Note any limitations in the available evidence"""

COMPARE_USER = """Compare the following based on the provided context:

Comparison query: {query}

Context from previous searches:
{context}

Provide a structured comparison."""
