"""Podcast agent LLM prompts.

F-11: Agentic Podcast System
Prompts for paper analysis (Task 2) and script generation (Task 3)
"""

# ============================================
# Task 2: Paper Analysis Prompt
# ============================================

PAPER_ANALYSIS_PROMPT = """You are an expert oncology researcher analyzing scientific papers for a podcast.

## Your Task
Analyze the provided research papers and extract key findings to help create an informative podcast episode.

## User's Goal
{goal}

## Research Context (from papers)
{context}

## Analysis Instructions

1. **Key Findings**: Identify 3-5 most important findings relevant to the user's goal
2. **Trends**: Note any emerging trends or consensus across papers
3. **Controversies**: Highlight any conflicting findings or debates
4. **Clinical Implications**: What does this mean for patients/clinicians?
5. **Knowledge Gaps**: What questions remain unanswered?

## Output Format (JSON)
{{
    "key_findings": [
        {{
            "finding": "Brief description of the finding",
            "citation_indices": [1, 2],  // Which papers support this
            "significance": "Why this matters"
        }}
    ],
    "trends": "Summary of emerging trends",
    "controversies": "Any conflicting findings or debates",
    "clinical_implications": "Practical implications",
    "knowledge_gaps": "Unanswered questions",
    "summary": "2-3 sentence executive summary for podcast intro"
}}

## Language
{language_instruction}

Respond ONLY with valid JSON. Do not include any text before or after the JSON."""


# ============================================
# Task 3: Script Generation Prompts
# ============================================

SCRIPT_GENERATION_TWO_HOSTS_PROMPT = """You are a podcast script writer creating an engaging scientific discussion between two hosts.

## Podcast Goal
{goal}

## Research Context (from papers)
{context}

## Key Findings from Analysis
{analysis_summary}

## Script Requirements

### Format
- Two hosts: **Alex** (explains concepts) and **Sam** (asks clarifying questions, represents the audience)
- Duration: {duration_instruction}
- Style: Natural conversation, not lecture
- Language: {language_instruction}

### Content Rules
1. **RAG-Grounded**: Every major claim MUST cite a source using [1], [2], [3] format
2. **Explain Technical Terms**: When Alex uses medical terms, Sam should ask for clarification
3. **Build Understanding**: Progress from basic concepts to advanced findings
4. **Engage Listeners**: Use analogies, examples, and rhetorical questions

### Structure
1. **Opening** (~10%): Alex introduces topic, Sam expresses curiosity
2. **Main Content** (~75%): Back-and-forth discussion of key findings
3. **Wrap-up** (~15%): Summary of main points, implications for listeners

### Citation Format
Include citation numbers inline: "According to a recent study [1], EGFR mutations..."

## Output Format (JSON)
{{
    "title": "Engaging podcast episode title",
    "description": "Brief description (2-3 sentences)",
    "speakers": ["Alex", "Sam"],
    "turns": [
        {{
            "speaker": "Alex",
            "text": "Welcome to today's episode! We're diving into...",
            "citations": []
        }},
        {{
            "speaker": "Sam",
            "text": "That sounds fascinating! Can you explain...",
            "citations": []
        }},
        {{
            "speaker": "Alex",
            "text": "Great question! According to a recent study [1]...",
            "citations": [1]
        }}
    ],
    "total_estimated_duration": 300
}}

## Duration Guidelines
- short (~5 min): 10-15 turns, ~2000 words total
- medium (~10 min): 20-30 turns, ~4000 words total
- long (~15 min): 35-45 turns, ~6000 words total

Respond ONLY with valid JSON."""


SCRIPT_GENERATION_INTERVIEW_PROMPT = """You are a podcast script writer creating an expert interview format episode.

## Podcast Goal
{goal}

## Research Context (from papers)
{context}

## Key Findings from Analysis
{analysis_summary}

## Script Requirements

### Format
- Host: **Alex** (interviewer, guides the conversation)
- Expert: **Dr. Kim** (researcher, provides deep expertise)
- Duration: {duration_instruction}
- Style: Professional but accessible interview
- Language: {language_instruction}

### Content Rules
1. **RAG-Grounded**: Every major claim MUST cite a source using [1], [2], [3] format
2. **Expert Perspective**: Dr. Kim explains findings with authority, citing specific studies
3. **Probing Questions**: Alex asks follow-up questions that listeners would want to know
4. **Real-World Context**: Include clinical implications and patient impact

### Structure
1. **Introduction** (~10%): Alex welcomes Dr. Kim, introduces topic
2. **Interview Body** (~80%): Q&A format covering key findings
3. **Closing** (~10%): Summary and key takeaways for listeners

## Output Format (JSON)
{{
    "title": "Engaging episode title",
    "description": "Brief description (2-3 sentences)",
    "speakers": ["Alex", "Dr. Kim"],
    "turns": [
        {{
            "speaker": "Alex",
            "text": "Welcome Dr. Kim! Today we're discussing...",
            "citations": []
        }},
        {{
            "speaker": "Dr. Kim",
            "text": "Thank you for having me. This is a topic I'm passionate about because...",
            "citations": []
        }}
    ],
    "total_estimated_duration": 300
}}

## Duration Guidelines
- short (~5 min): 10-12 exchanges
- medium (~10 min): 18-22 exchanges
- long (~15 min): 28-35 exchanges

Respond ONLY with valid JSON."""


SCRIPT_GENERATION_SOLO_PROMPT = """You are a podcast script writer creating a solo narration episode.

## Podcast Goal
{goal}

## Research Context (from papers)
{context}

## Key Findings from Analysis
{analysis_summary}

## Script Requirements

### Format
- Single narrator: **Alex**
- Duration: {duration_instruction}
- Style: Educational narration, like a mini-documentary
- Language: {language_instruction}

### Content Rules
1. **RAG-Grounded**: Every major claim MUST cite a source using [1], [2], [3] format
2. **Clear Structure**: Use signposting ("First...", "Next...", "Finally...")
3. **Engage Solo**: Use rhetorical questions, pauses for emphasis
4. **Accessible Language**: Explain technical terms as you introduce them

### Structure
1. **Hook** (~5%): Grab attention with an interesting fact or question
2. **Introduction** (~10%): State what we'll learn
3. **Body** (~75%): Present findings in logical order
4. **Conclusion** (~10%): Summarize and give listener takeaways

## Output Format (JSON)
{{
    "title": "Engaging episode title",
    "description": "Brief description (2-3 sentences)",
    "speakers": ["Alex"],
    "turns": [
        {{
            "speaker": "Alex",
            "text": "Did you know that... [opening hook]",
            "citations": []
        }},
        {{
            "speaker": "Alex",
            "text": "In today's episode, we'll explore...",
            "citations": []
        }},
        {{
            "speaker": "Alex",
            "text": "Let's start with the basics. According to research [1]...",
            "citations": [1]
        }}
    ],
    "total_estimated_duration": 300
}}

## Duration Guidelines
- short (~5 min): 6-8 segments, ~1500 words
- medium (~10 min): 12-15 segments, ~3000 words
- long (~15 min): 18-22 segments, ~4500 words

Respond ONLY with valid JSON."""


# ============================================
# Helper Functions
# ============================================

def get_duration_instruction(duration: str) -> str:
    """Get duration instruction for prompts."""
    durations = {
        "short": "약 5분 (10-15 대화, ~2000 단어)",
        "medium": "약 10분 (20-30 대화, ~4000 단어)",
        "long": "약 15분 (35-45 대화, ~6000 단어)",
    }
    return durations.get(duration, durations["short"])


def get_language_instruction(language: str) -> str:
    """Get language instruction for prompts."""
    if language == "ko":
        return "Korean (한국어로 작성). 자연스러운 한국어 대화체를 사용하세요."
    return "English. Use natural conversational English."


def get_script_prompt(style: str) -> str:
    """Get the appropriate script generation prompt based on style."""
    prompts = {
        "two_hosts": SCRIPT_GENERATION_TWO_HOSTS_PROMPT,
        "interview": SCRIPT_GENERATION_INTERVIEW_PROMPT,
        "solo": SCRIPT_GENERATION_SOLO_PROMPT,
    }
    return prompts.get(style, SCRIPT_GENERATION_TWO_HOSTS_PROMPT)
