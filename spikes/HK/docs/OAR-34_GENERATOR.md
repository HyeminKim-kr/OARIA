# OAR-34: LLM Generator & Prompt Templates Implementation

> **Jira Ticket**: OAR-34
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/generator.py`

---

## Summary

Implemented an LLM-based answer generator using Claude API that synthesizes information from retrieved sources with strict citation requirements, safety guidelines, and streaming support.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| Use only provided paper info | System prompt enforces "ONLY use provided sources" |
| [PMID:number] citation format | Changed to [1], [2] for simplicity; mapped to paper IDs |
| Explicitly state uncertainty | Prompt includes "If sources don't contain enough info, say so" |
| No clinical recommendations | System prompt: "NEVER provide clinical advice" |
| System/user prompt separation | `SYSTEM_PROMPT` + `CONTEXT_PROMPT_TEMPLATE` |
| Streaming response support | `generate_stream()` method |
| Token limit management | `max_context_tokens`, `max_tokens` in config |

---

## Design Decisions

### 1. Why Claude API?

| Feature | Claude | GPT-4 | Open Source |
|---------|--------|-------|-------------|
| Instruction following | Excellent | Good | Variable |
| Citation compliance | Strong | Good | Weak |
| Scientific text | Very good | Very good | Moderate |
| Streaming | Yes | Yes | Depends |
| Cost | Moderate | Higher | Free but infra cost |

**Reasoning:**
- Claude excels at following complex citation rules
- Strong performance on scientific/medical text
- Native streaming for better UX
- Good balance of quality and cost

### 2. Why Low Temperature (0.3)?

```
┌─────────────────────────────────────────────────────────────────┐
│  Temperature Effect on RAG Outputs                              │
│                                                                 │
│  temp=0.0: Deterministic, repetitive, may miss nuance          │
│  temp=0.3: Factual, consistent, slight variation  ← CHOSEN     │
│  temp=0.7: Creative, diverse, some hallucination risk          │
│  temp=1.0: Very creative, high hallucination risk              │
└─────────────────────────────────────────────────────────────────┘
```

**Why 0.3?**
- RAG requires factual accuracy (rely on sources, not creativity)
- Low but not zero to allow natural language variation
- Reduces hallucination risk significantly
- Tested to give consistent citation behavior

### 3. Why Numbered Citations [1], [2]?

**Original requirement**: `[PMID:12345678]`

**Changed to**: `[1]`, `[2]`, `[3]`...

**Reasoning:**
1. **Not all papers have PMIDs**: OpenAlex papers may have DOI, OpenAlex ID, but not PMID
2. **Shorter prompts**: `[1]` vs `[PMID:12345678]` saves tokens
3. **Easier parsing**: Simple regex `\[(\d+)\]`
4. **LLM compliance**: LLMs follow numbered references more reliably
5. **Citation Linker (OAR-35)**: Maps [1] → paper_id in post-processing

### 4. Why Strict System Prompt?

```python
SYSTEM_PROMPT = """
## Critical Rules

### 1. Citation Requirements
- EVERY factual claim MUST have a citation
- Use format: [1], [2], etc.
...

### 3. Safety Guidelines
- NEVER provide clinical recommendations
- Always recommend consulting healthcare professionals
...
"""
```

**Why so explicit?**
- LLMs follow clear, enumerated rules better than vague instructions
- "NEVER" and "MUST" are strong instructions that Claude respects
- Safety rules are non-negotiable in medical domain
- Repeated testing showed this format maximizes compliance

### 5. Why Separate System/User Prompts?

```
┌─────────────────────────────────────────────────────────────────┐
│  System Prompt (constant)                                       │
│  - Role definition                                              │
│  - Citation rules                                               │
│  - Safety guidelines                                            │
│  - Response format                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  User Prompt (variable)                                         │
│  - Retrieved context                                            │
│  - User's question                                              │
│  - Specific instructions                                        │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- System prompt cached by some providers (cost savings)
- Easy A/B testing of prompts
- Clear separation of concerns
- Easier prompt version management

---

## Prompt Templates

### System Prompt

```
You are OARIA (Oncology AI Research Intelligence Assistant)...

## Critical Rules

### 1. Citation Requirements
- EVERY factual claim MUST have a citation
- Use format: [1], [2], etc. matching the source numbers
- Never make claims without citation support

### 2. Honesty About Limitations
- If the provided sources don't contain enough information, say so clearly
- Use phrases like "Based on the provided sources..."

### 3. Safety Guidelines
- NEVER provide clinical recommendations or treatment advice
- Always recommend consulting healthcare professionals

### 4. Response Format
- Start with a direct answer
- Support with evidence from sources
- Use clear, organized structure

### 5. Language
- Respond in the same language as the user's question
```

### Context Prompt Template

```
## Research Context

The following excerpts are from peer-reviewed oncology papers.
Use these as your ONLY source of information.

{context}

---

## User Question

{question}

---

## Instructions

Answer the question using ONLY the information from the provided paper excerpts.
Follow the citation rules strictly.
```

---

## Implementation Details

### Generation Flow

```
Input:
  question = "What is EGFR inhibitor efficacy?"
  sources = [
    {text: "...", paper_id: "W001", score: 0.92},
    {text: "...", paper_id: "W002", score: 0.88},
  ]

Step 1: Format Context
  [1] Source: W001 (relevance: 0.92)
  EGFR mutations are found in...

  [2] Source: W002 (relevance: 0.88)
  Erlotinib shows 70% response rate...

Step 2: Build Messages
  system = SYSTEM_PROMPT
  user = CONTEXT_PROMPT_TEMPLATE.format(context, question)

Step 3: Call Claude API
  response = client.messages.create(...)

Step 4: Extract Metadata
  answer = response.content[0].text
  citations_used = extract_citations(answer)  # [1, 2]

Output:
  GeneratorOutput(
    answer="EGFR inhibitors show significant efficacy... [1] Response rates... [2]",
    citations_used=[1, 2],
    input_tokens=1500,
    output_tokens=400,
    generation_time_ms=2500,
  )
```

### Streaming Support

```python
# Non-streaming (wait for full response)
output = generator.generate(question, sources)
print(output.answer)

# Streaming (print as generated)
for chunk in generator.generate_stream(question, sources):
    print(chunk, end="", flush=True)
```

**Why streaming?**
- Better UX for long answers (user sees progress)
- Lower perceived latency
- Can cancel mid-generation if needed

---

## Usage Examples

### Basic Generation

```python
from generator import LLMGenerator

generator = LLMGenerator()

sources = [
    {"text": "EGFR mutations...", "paper_id": "W001", "score": 0.92},
    {"text": "Erlotinib shows...", "paper_id": "W002", "score": 0.88},
]

output = generator.generate(
    question="What is EGFR inhibitor efficacy?",
    sources=sources,
)

print(output.answer)
print(f"Citations used: {output.citations_used}")
```

### With Configuration

```python
from generator import LLMGenerator, GeneratorConfig

config = GeneratorConfig(
    model="claude-sonnet-4-20250514",
    max_tokens=2048,
    temperature=0.3,
)

generator = LLMGenerator(config=config)
```

### Streaming

```python
print("Answer: ", end="")
for chunk in generator.generate_stream(question, sources):
    print(chunk, end="", flush=True)
print()  # Newline at end
```

### Full Pipeline Integration

```python
from retriever import Retriever
from reranker import CrossEncoderReranker
from generator import LLMGenerator

# Initialize
retriever = Retriever(...)
reranker = CrossEncoderReranker()
generator = LLMGenerator()

# Process query
query = "What are EGFR inhibitors?"

# Stage 1: Retrieve
retrieval = retriever.retrieve(query, top_k=20)

# Stage 2: Rerank
reranked = reranker.rerank_retrieval_result(query, retrieval.results, top_n=5)

# Stage 3: Generate
sources = [r.to_dict() for r in reranked.results]
output = generator.generate(query, sources)

print(output.answer)
```

---

## Token Budget Management

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Context Window: 200K tokens                             │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ System Prompt:        ~800 tokens                         │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ Context (sources):    ~6000 tokens max (configurable)     │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ Question:             ~500 tokens max                     │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ Response:             ~2048 tokens max (configurable)     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Total budget: ~10,000 tokens per request                      │
└─────────────────────────────────────────────────────────────────┘
```

**Why limit context?**
- Cost control (tokens = money)
- Quality (too much context → model loses focus)
- 5-7 relevant sources usually sufficient
- Reranker already selected best matches

---

## Output Example

**Question**: "What is the efficacy of EGFR inhibitors in lung cancer?"

**Generated Answer**:
```
Based on the provided research sources, EGFR inhibitors demonstrate
significant efficacy in treating EGFR-mutant non-small cell lung cancer
(NSCLC).

**Response Rates and Survival:**
First-generation EGFR tyrosine kinase inhibitors (TKIs) such as erlotinib
and gefitinib show response rates of 60-70% in patients with EGFR mutations,
with median progression-free survival of 9-13 months [2].

**Patient Selection:**
EGFR mutations, particularly exon 19 deletions and L858R point mutations,
are found in approximately 15% of NSCLC patients in Western populations
and up to 50% in Asian populations [1]. These mutations serve as predictive
biomarkers for TKI sensitivity.

**Third-Generation TKIs:**
Osimertinib, a third-generation EGFR TKI, addresses the limitation of
acquired resistance through T790M mutation. The FLAURA trial demonstrated
superior overall survival compared to first-generation TKIs [3].

*Note: This information is based on research findings. For clinical decisions,
please consult with healthcare professionals.*
```

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Generation time | 2-5 seconds |
| Input tokens (typical) | 1500-3000 |
| Output tokens (typical) | 300-800 |
| Cost per query | ~$0.01-0.03 (Claude Sonnet) |

---

## Limitations & Future Improvements

### Current Limitations

1. **Single model**: Only Claude API supported
2. **No caching**: Same question regenerates
3. **English prompt**: Multi-lingual responses work, but prompt is English
4. **No retry logic**: API errors not automatically retried

### Potential Improvements

1. **Multi-model support**: Add OpenAI, local LLMs
2. **Response caching**: Cache answers for repeated questions
3. **Prompt localization**: Translate system prompt for better non-English
4. **Retry with backoff**: Handle rate limits gracefully

---

## File Location

```
/spikes/HK/src/generator.py
```

---

## Related Tickets

- **OAR-33**: Reranker (provides input sources)
- **OAR-35**: Citation Linker (processes output citations)
- **OAR-36**: RAG Pipeline (orchestrates all components)
