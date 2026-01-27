# F-11: Agentic Podcast System

> **Feature ID**: F-11
> **Status**: Implementation Phase
> **Owner**: 김혜민
> **Created**: 2025-01-16
> **Updated**: 2025-01-19
> **Timeline**: 3 days (MVP)

---

## 1. Overview

### 1.1 What is it?

The Agentic Podcast System automatically generates podcast episodes from research papers using LLM for script generation and TTS for audio synthesis. Users can trigger generation manually or via scheduled Celery tasks.

### 1.2 MVP Scope (3 Days)

| Included (MVP) | Deferred (Post-MVP) |
|----------------|---------------------|
| Episode Generator Agent | Paper Monitor Agent (use existing DB papers) |
| TTS Service (OpenAI) | Email/RSS Delivery (download link only) |
| Celery Scheduling | Importance Scorer Agent (simple selection) |
| Subscription Preferences | Publisher Agent |
| API Endpoints | `paper_scores` table |
| 2 DB Tables | `episode_deliveries` table |

### 1.3 What is it? (Full Vision)

The full Agentic Podcast System automatically monitors research papers, detects important publications, and generates podcast episodes without human intervention. Users subscribe to topics and receive auto-generated audio content explaining new research in accessible language.

### 1.2 Why is it Agentic?

| Traditional Tool | Agentic System |
|------------------|----------------|
| User requests → Output | System proactively creates content |
| Reactive | Autonomous |
| One-time generation | Continuous monitoring + publishing |
| Manual trigger | Scheduled + event-driven |

### 1.3 Use Cases

**Oncology Researchers:**
- "Subscribe to EGFR mutation research" → Weekly podcast of new findings
- Auto-episode when landmark paper published in Nature/Cell

**Climate Change Stakeholders:**
- "Subscribe to Arctic ice melt studies" → Bi-weekly updates
- Breaking episode when IPCC releases new data

**Cross-Domain:**
- "Climate + Cancer intersection" → Monthly digest of environmental oncology

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OARIA AGENTIC PODCAST SYSTEM                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                              AGENT LAYER                                     │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │   Paper     │   │ Importance  │   │  Episode    │   │  Publisher  │      │
│  │  Monitor    │──▶│   Scorer    │──▶│  Generator  │──▶│    Agent    │      │
│  │   Agent     │   │   Agent     │   │   Agent     │   │             │      │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘      │
│        │                                                      │              │
│        │ (Cron: daily)                                       │              │
│        ▼                                                      ▼              │
│  ┌─────────────┐                                       ┌─────────────┐      │
│  │  OpenAlex   │                                       │   Delivery  │      │
│  │    API      │                                       │  Channels   │      │
│  └─────────────┘                                       │ (Email/RSS) │      │
│                                                        └─────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
         │                                                      │
         ▼                                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            SERVICE LAYER                                     │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │   Paper     │   │    LLM      │   │    TTS      │   │   Storage   │      │
│  │  Service    │   │   Service   │   │   Service   │   │   Service   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
         │                   │                  │                 │
         ▼                   ▼                  ▼                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │ PostgreSQL  │   │  Weaviate   │   │    Redis    │   │    MinIO    │      │
│  │  (metadata) │   │  (vectors)  │   │   (queue)   │   │   (files)   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Details

#### Paper Monitor Agent *(Deferred to Post-MVP)*
> **MVP Alternative**: Use existing papers in PostgreSQL database instead of fetching new ones from OpenAlex.

- **Trigger**: Cron job (daily at 6 AM)
- **Function**: Fetches new papers from OpenAlex based on subscribed topics
- **Output**: List of candidate papers for scoring

#### Importance Scorer Agent
- **Input**: Candidate papers
- **Function**: Scores papers on episode-worthiness
- **Criteria**:
  - Citation velocity (early citations)
  - Journal impact factor
  - Author reputation
  - Novelty score (contradiction to existing research)
  - Public interest potential
- **Output**: Ranked papers with scores

#### Episode Generator Agent
- **Input**: High-scoring papers (score > threshold)
- **Function**: Creates podcast script + audio
- **Steps**:
  1. Retrieve full paper context
  2. Generate dialogue script via LLM
  3. Convert to audio via TTS
  4. Add intro/outro music
  5. Generate episode metadata (title, description, chapters)
- **Output**: Complete episode package

#### Publisher Agent *(Deferred to Post-MVP)*
> **MVP Alternative**: Episodes are saved to database with download link. No email/RSS delivery.

- **Input**: Episode package
- **Function**: Distributes to subscribers
- **Channels**:
  - Email notification with player link
  - RSS feed update
  - In-app notification
  - (Future) Spotify/Apple Podcasts

---

## 3. Data Models

### 3.1 Database Schema

```sql
-- Podcast subscriptions
CREATE TABLE podcast_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),

    -- Topic configuration
    topics TEXT[] NOT NULL,                    -- ['EGFR', 'immunotherapy']
    domains TEXT[] DEFAULT ARRAY['oncology'], -- ['oncology', 'climate']

    -- Delivery preferences
    frequency VARCHAR(20) DEFAULT 'weekly',   -- daily, weekly, monthly, breaking
    delivery_channels TEXT[] DEFAULT ARRAY['email'],

    -- Content preferences
    episode_style VARCHAR(20) DEFAULT 'two_hosts',  -- two_hosts, interview, solo
    episode_duration VARCHAR(10) DEFAULT 'short',   -- short (5min), medium (10min), long (15min)
    language VARCHAR(5) DEFAULT 'en',

    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Generated episodes
CREATE TABLE podcast_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Episode metadata
    title VARCHAR(500) NOT NULL,
    description TEXT,
    duration_seconds INTEGER,
    word_count INTEGER,

    -- Source papers
    paper_ids TEXT[] NOT NULL,
    primary_paper_id VARCHAR(50),

    -- Content
    script_url VARCHAR(500),
    audio_url VARCHAR(500),
    thumbnail_url VARCHAR(500),

    -- Classification
    topics TEXT[],
    domain VARCHAR(50),
    episode_style VARCHAR(20),
    language VARCHAR(5),

    -- Scoring (why this episode was created)
    importance_score FLOAT,
    scoring_reasons JSONB,

    -- Status
    status VARCHAR(20) DEFAULT 'draft',  -- draft, published, archived
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============ DEFERRED TO POST-MVP ============

-- Episode delivery tracking (Deferred: MVP uses download link only)
-- CREATE TABLE episode_deliveries (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     episode_id UUID REFERENCES podcast_episodes(id),
--     subscription_id UUID REFERENCES podcast_subscriptions(id),
--     user_id UUID REFERENCES users(id),
--     channel VARCHAR(20),
--     delivered_at TIMESTAMP,
--     opened_at TIMESTAMP,
--     listened_at TIMESTAMP,
--     listen_duration_seconds INTEGER,
--     created_at TIMESTAMP DEFAULT NOW()
-- );

-- Paper scoring history (Deferred: MVP uses simple selection without scoring history)
-- CREATE TABLE paper_scores (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     paper_id VARCHAR(50) NOT NULL,
--     total_score FLOAT,
--     citation_score FLOAT,
--     journal_score FLOAT,
--     novelty_score FLOAT,
--     public_interest_score FLOAT,
--     selected_for_episode BOOLEAN,
--     episode_id UUID REFERENCES podcast_episodes(id),
--     scored_at TIMESTAMP DEFAULT NOW()
-- );
```

### 3.2 Pydantic Models

```python
# backend/app/schemas/podcast.py

from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class EpisodeStyle(str, Enum):
    TWO_HOSTS = "two_hosts"
    INTERVIEW = "interview"
    SOLO = "solo_explainer"

class EpisodeDuration(str, Enum):
    SHORT = "short"      # ~5 min
    MEDIUM = "medium"    # ~10 min
    LONG = "long"        # ~15 min

class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    BREAKING = "breaking"  # Immediate for high-impact papers

class DeliveryChannel(str, Enum):
    EMAIL = "email"
    RSS = "rss"
    PUSH = "push"
    IN_APP = "in_app"


class SubscriptionCreate(BaseModel):
    topics: list[str]
    domains: list[str] = ["oncology"]
    frequency: Frequency = Frequency.WEEKLY
    delivery_channels: list[DeliveryChannel] = [DeliveryChannel.EMAIL]
    episode_style: EpisodeStyle = EpisodeStyle.TWO_HOSTS
    episode_duration: EpisodeDuration = EpisodeDuration.SHORT
    language: str = "en"


class SubscriptionResponse(BaseModel):
    id: str
    topics: list[str]
    domains: list[str]
    frequency: Frequency
    is_active: bool
    created_at: datetime


class DialogueSegment(BaseModel):
    speaker: str          # "host1", "host2", "expert"
    name: str            # "Alex", "Sam"
    text: str
    emotion: str = "neutral"  # For TTS expressiveness


class EpisodeScript(BaseModel):
    title: str
    description: str
    dialogue: list[DialogueSegment]
    chapters: list[dict]  # [{"time": 0, "title": "Introduction"}, ...]


class EpisodeResponse(BaseModel):
    id: str
    title: str
    description: str
    duration_seconds: int
    audio_url: str
    script_url: str
    paper_ids: list[str]
    topics: list[str]
    importance_score: float
    published_at: datetime | None


class PaperScore(BaseModel):
    paper_id: str
    title: str
    total_score: float
    citation_score: float
    journal_score: float
    novelty_score: float
    public_interest_score: float
    reasons: list[str]
```

---

## 4. Agent Implementation

### 4.1 Paper Monitor Agent *(Deferred to Post-MVP)*

> **MVP**: Skip this agent. Use existing papers from PostgreSQL database via simple query.

```python
# backend/app/services/podcast/agents/monitor.py (POST-MVP)

import asyncio
from datetime import datetime, timedelta
from app.services.openalex import OpenAlexClient
from app.models.podcast import PodcastSubscription

class PaperMonitorAgent:
    """
    Autonomous agent that monitors OpenAlex for new papers
    matching user subscriptions.

    Runs: Daily at 6 AM (configurable)
    """

    def __init__(
        self,
        openalex_client: OpenAlexClient,
        subscription_repo: SubscriptionRepository,
    ):
        self.openalex = openalex_client
        self.subscriptions = subscription_repo
        self.lookback_days = 7  # Check papers from last 7 days

    async def run(self) -> list[CandidatePaper]:
        """
        Main agent loop.
        Returns list of candidate papers for scoring.
        """
        # 1. Get all active subscriptions
        subscriptions = await self.subscriptions.get_active()

        # 2. Aggregate unique topics across all subscriptions
        all_topics = self._aggregate_topics(subscriptions)

        # 3. Fetch recent papers for each topic
        candidates = []
        for topic in all_topics:
            papers = await self._fetch_papers_for_topic(topic)
            candidates.extend(papers)

        # 4. Deduplicate
        unique_candidates = self._deduplicate(candidates)

        logger.info(
            "Paper monitor completed",
            total_subscriptions=len(subscriptions),
            topics_searched=len(all_topics),
            candidates_found=len(unique_candidates)
        )

        return unique_candidates

    async def _fetch_papers_for_topic(self, topic: str) -> list[CandidatePaper]:
        """Fetch recent papers from OpenAlex for a topic."""
        since_date = datetime.now() - timedelta(days=self.lookback_days)

        papers = await self.openalex.search_papers(
            query=topic,
            from_date=since_date,
            filter_open_access=True,  # Only OA papers (we need full text)
            sort_by="cited_by_count",
            limit=50
        )

        return [
            CandidatePaper(
                paper_id=p.openalex_id,
                title=p.title,
                abstract=p.abstract,
                authors=p.authors,
                journal=p.journal,
                publication_date=p.publication_date,
                cited_by_count=p.cited_by_count,
                topics=[topic],
                open_access_url=p.open_access_url,
            )
            for p in papers
        ]

    def _aggregate_topics(self, subscriptions: list[PodcastSubscription]) -> set[str]:
        """Get unique topics from all subscriptions."""
        topics = set()
        for sub in subscriptions:
            topics.update(sub.topics)
        return topics

    def _deduplicate(self, candidates: list[CandidatePaper]) -> list[CandidatePaper]:
        """Remove duplicate papers, merge topics."""
        seen = {}
        for candidate in candidates:
            if candidate.paper_id in seen:
                # Merge topics
                seen[candidate.paper_id].topics.extend(candidate.topics)
            else:
                seen[candidate.paper_id] = candidate
        return list(seen.values())
```

### 4.2 Importance Scorer Agent

```python
# backend/app/services/podcast/agents/scorer.py

from app.services.llm import LLMService

class ImportanceScorerAgent:
    """
    Scores papers on their episode-worthiness.
    Uses both heuristics and LLM judgment.

    Scoring Criteria:
    - Citation velocity (0-25 points)
    - Journal impact (0-25 points)
    - Novelty/contradiction (0-25 points)
    - Public interest (0-25 points)

    Total: 0-100 points
    Threshold for episode: 60 points
    """

    EPISODE_THRESHOLD = 60
    BREAKING_THRESHOLD = 85  # Immediate episode for very important papers

    # Journal tiers (from CLAUDE.md ADR)
    TIER1_JOURNALS = ["Nature", "Science", "Cell", "NEJM", "Lancet", "Cancer Cell", "JCO"]
    TIER2_JOURNALS = ["Cancer Research", "Blood", "PNAS", "Nature Communications"]

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def score_papers(
        self,
        candidates: list[CandidatePaper]
    ) -> list[ScoredPaper]:
        """Score all candidate papers."""
        scored = []

        for paper in candidates:
            score = await self._score_paper(paper)
            scored.append(score)

        # Sort by total score descending
        scored.sort(key=lambda x: x.total_score, reverse=True)

        return scored

    async def _score_paper(self, paper: CandidatePaper) -> ScoredPaper:
        """Calculate importance score for a single paper."""

        # 1. Citation score (0-25)
        citation_score = self._calculate_citation_score(paper)

        # 2. Journal score (0-25)
        journal_score = self._calculate_journal_score(paper)

        # 3. Novelty score via LLM (0-25)
        novelty_score, novelty_reasons = await self._calculate_novelty_score(paper)

        # 4. Public interest score via LLM (0-25)
        public_score, public_reasons = await self._calculate_public_interest_score(paper)

        total_score = citation_score + journal_score + novelty_score + public_score

        reasons = []
        if citation_score >= 20:
            reasons.append(f"High citation velocity ({paper.cited_by_count} citations)")
        if journal_score >= 20:
            reasons.append(f"Published in top-tier journal ({paper.journal})")
        reasons.extend(novelty_reasons)
        reasons.extend(public_reasons)

        return ScoredPaper(
            paper=paper,
            total_score=total_score,
            citation_score=citation_score,
            journal_score=journal_score,
            novelty_score=novelty_score,
            public_interest_score=public_score,
            reasons=reasons,
            is_breaking=total_score >= self.BREAKING_THRESHOLD,
            should_generate=total_score >= self.EPISODE_THRESHOLD,
        )

    def _calculate_citation_score(self, paper: CandidatePaper) -> float:
        """
        Score based on citation count relative to paper age.
        New papers with citations = high velocity = important.
        """
        days_since_publication = (datetime.now() - paper.publication_date).days
        if days_since_publication == 0:
            days_since_publication = 1

        # Citations per day
        velocity = paper.cited_by_count / days_since_publication

        # Normalize to 0-25 scale
        # >1 citation/day = very high impact
        if velocity >= 1.0:
            return 25
        elif velocity >= 0.5:
            return 20
        elif velocity >= 0.1:
            return 15
        elif velocity >= 0.05:
            return 10
        else:
            return 5

    def _calculate_journal_score(self, paper: CandidatePaper) -> float:
        """Score based on journal prestige."""
        journal = paper.journal or ""

        for tier1 in self.TIER1_JOURNALS:
            if tier1.lower() in journal.lower():
                return 25

        for tier2 in self.TIER2_JOURNALS:
            if tier2.lower() in journal.lower():
                return 20

        # Check if it's a known journal at all
        if paper.journal:
            return 10

        return 5  # Preprint or unknown

    async def _calculate_novelty_score(
        self,
        paper: CandidatePaper
    ) -> tuple[float, list[str]]:
        """Use LLM to assess novelty/breakthrough potential."""

        prompt = f"""Analyze this research paper for novelty and breakthrough potential.

Title: {paper.title}
Abstract: {paper.abstract}

Score from 0-25 based on:
- Does it contradict existing consensus?
- Does it introduce a new method/approach?
- Does it solve a previously unsolved problem?
- Is it a first-of-its-kind study?

Return JSON:
{{
    "score": <0-25>,
    "reasons": ["reason1", "reason2"]
}}

Be strict. Most papers are incremental (score 5-10).
Only true breakthroughs get 20+."""

        response = await self.llm.generate(prompt, response_format="json")
        result = json.loads(response)

        return result["score"], result["reasons"]

    async def _calculate_public_interest_score(
        self,
        paper: CandidatePaper
    ) -> tuple[float, list[str]]:
        """Use LLM to assess public interest potential."""

        prompt = f"""Analyze this research paper for public interest potential.

Title: {paper.title}
Abstract: {paper.abstract}

Score from 0-25 based on:
- Would general public care about this finding?
- Does it affect daily life or health decisions?
- Is it newsworthy?
- Would it trend on social media?

Return JSON:
{{
    "score": <0-25>,
    "reasons": ["reason1", "reason2"]
}}

Be realistic. Most research is niche (score 5-10).
Only broadly impactful findings get 20+."""

        response = await self.llm.generate(prompt, response_format="json")
        result = json.loads(response)

        return result["score"], result["reasons"]
```

### 4.3 Episode Generator Agent

```python
# backend/app/services/podcast/agents/generator.py

class EpisodeGeneratorAgent:
    """
    Generates complete podcast episodes from scored papers.

    Output:
    - Dialogue script (JSON)
    - Audio file (MP3)
    - Metadata (title, description, chapters)
    """

    STYLE_PROMPTS = {
        "two_hosts": """You are writing a podcast script for two hosts discussing a research paper.

Host 1 (Alex): The explainer - clearly explains the research
Host 2 (Sam): The curious one - asks good questions, represents the listener

Guidelines:
- Natural, conversational tone
- Avoid jargon, explain technical terms
- Use analogies for complex concepts
- Include moments of genuine curiosity/excitement
- ~{word_count} words total""",

        "interview": """You are writing a podcast script where a host interviews a virtual expert about a research paper.

Host: Asks insightful questions
Expert: Provides detailed, authoritative answers

Guidelines:
- Professional but accessible tone
- Deep dive into methodology
- Address limitations and future directions
- ~{word_count} words total""",

        "solo_explainer": """You are writing a solo podcast script explaining a research paper.

Narrator: Clear, engaging, documentary-style

Guidelines:
- Storytelling approach
- Build narrative arc (problem → discovery → implications)
- Use vivid language
- ~{word_count} words total"""
    }

    DURATION_WORD_COUNTS = {
        "short": 750,    # ~5 minutes
        "medium": 1500,  # ~10 minutes
        "long": 2250,    # ~15 minutes
    }

    def __init__(
        self,
        llm_service: LLMService,
        tts_service: TTSService,
        storage_service: StorageService,
        paper_service: PaperService,
    ):
        self.llm = llm_service
        self.tts = tts_service
        self.storage = storage_service
        self.papers = paper_service

    async def generate_episode(
        self,
        scored_paper: ScoredPaper,
        style: EpisodeStyle = EpisodeStyle.TWO_HOSTS,
        duration: EpisodeDuration = EpisodeDuration.SHORT,
        language: str = "en",
    ) -> Episode:
        """Generate complete episode from scored paper."""

        # 1. Get full paper content
        paper = await self.papers.get_with_full_text(scored_paper.paper.paper_id)

        # 2. Generate script
        script = await self._generate_script(paper, style, duration, language)

        # 3. Generate audio
        audio_path = await self._generate_audio(script, style)

        # 4. Generate metadata
        metadata = await self._generate_metadata(paper, script, scored_paper)

        # 5. Upload files
        script_url = await self.storage.upload_json(script.dict(), "scripts")
        audio_url = await self.storage.upload_file(audio_path, "audio")

        # 6. Create episode record
        episode = Episode(
            title=metadata["title"],
            description=metadata["description"],
            duration_seconds=metadata["duration"],
            word_count=self._count_words(script),
            paper_ids=[paper.openalex_id],
            primary_paper_id=paper.openalex_id,
            script_url=script_url,
            audio_url=audio_url,
            topics=scored_paper.paper.topics,
            domain=paper.domain,
            episode_style=style,
            language=language,
            importance_score=scored_paper.total_score,
            scoring_reasons=scored_paper.reasons,
            status="draft",
        )

        return episode

    async def _generate_script(
        self,
        paper: Paper,
        style: EpisodeStyle,
        duration: EpisodeDuration,
        language: str,
    ) -> EpisodeScript:
        """Generate dialogue script via LLM."""

        word_count = self.DURATION_WORD_COUNTS[duration]
        system_prompt = self.STYLE_PROMPTS[style].format(word_count=word_count)

        user_prompt = f"""Create a podcast episode about this research paper.

PAPER INFORMATION:
Title: {paper.title}
Authors: {', '.join(paper.authors[:5])}
Journal: {paper.journal}
Publication Date: {paper.publication_date}

Abstract:
{paper.abstract}

Key Findings (from full text):
{self._extract_key_findings(paper.full_text)}

REQUIREMENTS:
1. Start with engaging hook
2. Explain the research question
3. Describe methodology (simplified)
4. Present key findings
5. Discuss implications
6. End with takeaway message

Language: {language}

Return JSON format:
{{
    "title": "Episode title",
    "description": "2-3 sentence description",
    "dialogue": [
        {{"speaker": "host1", "name": "Alex", "text": "..."}},
        {{"speaker": "host2", "name": "Sam", "text": "..."}},
        ...
    ],
    "chapters": [
        {{"time": 0, "title": "Introduction"}},
        {{"time": 60, "title": "The Research Question"}},
        ...
    ]
}}"""

        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format="json",
            model="claude-3-5-sonnet"  # Use best model for quality
        )

        return EpisodeScript(**json.loads(response))

    async def _generate_audio(
        self,
        script: EpisodeScript,
        style: EpisodeStyle,
    ) -> str:
        """Convert script to audio via TTS."""

        # Voice mapping
        voices = {
            "two_hosts": {"host1": "alloy", "host2": "nova"},
            "interview": {"host": "alloy", "expert": "onyx"},
            "solo_explainer": {"narrator": "nova"},
        }

        voice_map = voices[style]
        audio_segments = []

        for segment in script.dialogue:
            voice = voice_map.get(segment.speaker, "alloy")

            audio = await self.tts.synthesize(
                text=segment.text,
                voice=voice,
            )
            audio_segments.append(audio)

            # Add small pause between speakers
            audio_segments.append(self._generate_silence(300))  # 300ms

        # Concatenate all segments
        final_audio = self._concatenate_audio(audio_segments)

        # Add intro/outro music (optional)
        final_audio = self._add_music(final_audio)

        # Export to temp file
        temp_path = f"/tmp/episode_{uuid4()}.mp3"
        final_audio.export(temp_path, format="mp3")

        return temp_path

    async def _generate_metadata(
        self,
        paper: Paper,
        script: EpisodeScript,
        scored_paper: ScoredPaper,
    ) -> dict:
        """Generate episode metadata."""

        # Calculate duration from word count (avg 150 words/min)
        word_count = sum(len(s.text.split()) for s in script.dialogue)
        duration_seconds = int((word_count / 150) * 60)

        return {
            "title": script.title,
            "description": script.description,
            "duration": duration_seconds,
            "paper_title": paper.title,
            "paper_authors": paper.authors[:3],
            "importance_reasons": scored_paper.reasons,
        }
```

### 4.4 Publisher Agent *(Deferred to Post-MVP)*

> **MVP**: Skip this agent. Episodes saved to database with audio_url for direct download.

```python
# backend/app/services/podcast/agents/publisher.py (POST-MVP)

class PublisherAgent:
    """
    Distributes episodes to subscribers via configured channels.

    Channels:
    - Email: Send notification with player link
    - RSS: Update podcast feed
    - Push: In-app notification
    """

    def __init__(
        self,
        email_service: EmailService,
        rss_service: RSSService,
        notification_service: NotificationService,
        subscription_repo: SubscriptionRepository,
        delivery_repo: DeliveryRepository,
    ):
        self.email = email_service
        self.rss = rss_service
        self.notifications = notification_service
        self.subscriptions = subscription_repo
        self.deliveries = delivery_repo

    async def publish_episode(self, episode: Episode) -> PublishResult:
        """
        Publish episode to all matching subscribers.
        """

        # 1. Find matching subscriptions
        subscriptions = await self._find_matching_subscriptions(episode)

        # 2. Update RSS feed (once, for all RSS subscribers)
        await self.rss.add_episode(episode)

        # 3. Deliver to each subscriber
        deliveries = []
        for sub in subscriptions:
            for channel in sub.delivery_channels:
                delivery = await self._deliver(episode, sub, channel)
                deliveries.append(delivery)

        # 4. Update episode status
        episode.status = "published"
        episode.published_at = datetime.now()

        logger.info(
            "Episode published",
            episode_id=episode.id,
            title=episode.title,
            subscribers_notified=len(subscriptions),
            total_deliveries=len(deliveries)
        )

        return PublishResult(
            episode=episode,
            deliveries=deliveries,
            subscriber_count=len(subscriptions),
        )

    async def _find_matching_subscriptions(
        self,
        episode: Episode
    ) -> list[PodcastSubscription]:
        """Find subscriptions that match episode topics."""

        all_subs = await self.subscriptions.get_active()

        matching = []
        for sub in all_subs:
            # Check topic overlap
            topic_match = any(
                topic in episode.topics
                for topic in sub.topics
            )

            # Check domain match
            domain_match = episode.domain in sub.domains

            if topic_match and domain_match:
                matching.append(sub)

        return matching

    async def _deliver(
        self,
        episode: Episode,
        subscription: PodcastSubscription,
        channel: DeliveryChannel,
    ) -> EpisodeDelivery:
        """Deliver episode via specific channel."""

        if channel == DeliveryChannel.EMAIL:
            await self._send_email(episode, subscription)
        elif channel == DeliveryChannel.PUSH:
            await self._send_push(episode, subscription)
        elif channel == DeliveryChannel.IN_APP:
            await self._create_notification(episode, subscription)

        # Record delivery
        delivery = EpisodeDelivery(
            episode_id=episode.id,
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            channel=channel,
            delivered_at=datetime.now(),
        )

        await self.deliveries.create(delivery)
        return delivery

    async def _send_email(
        self,
        episode: Episode,
        subscription: PodcastSubscription,
    ):
        """Send email notification."""

        await self.email.send(
            to=subscription.user_email,
            subject=f"New Episode: {episode.title}",
            template="podcast_episode",
            data={
                "episode_title": episode.title,
                "description": episode.description,
                "duration": f"{episode.duration_seconds // 60} min",
                "listen_url": f"https://oaria.app/podcast/{episode.id}",
                "topics": episode.topics,
            }
        )
```

---

## 5. Scheduler & Orchestration

### 5.1 Celery Tasks

```python
# backend/app/tasks/podcast.py

from celery import shared_task
from app.services.podcast.orchestrator import PodcastOrchestrator

@shared_task(name="podcast.daily_monitor")
def daily_monitor_task():
    """
    Daily task to monitor papers and generate episodes.
    Runs at 6 AM daily.
    """
    orchestrator = PodcastOrchestrator()
    asyncio.run(orchestrator.run_daily_pipeline())


@shared_task(name="podcast.generate_episode")
def generate_episode_task(paper_id: str, subscription_ids: list[str]):
    """
    Generate episode for a specific paper.
    Called for breaking news (high-score papers).
    """
    orchestrator = PodcastOrchestrator()
    asyncio.run(orchestrator.generate_and_publish(paper_id, subscription_ids))


# Celery beat schedule
CELERY_BEAT_SCHEDULE = {
    "podcast-daily-monitor": {
        "task": "podcast.daily_monitor",
        "schedule": crontab(hour=6, minute=0),  # 6 AM daily
    },
}
```

### 5.2 Orchestrator

```python
# backend/app/services/podcast/orchestrator.py

class PodcastOrchestrator:
    """
    Coordinates all podcast agents in the pipeline.
    """

    def __init__(self):
        self.monitor = PaperMonitorAgent(...)
        self.scorer = ImportanceScorerAgent(...)
        self.generator = EpisodeGeneratorAgent(...)
        self.publisher = PublisherAgent(...)

    async def run_daily_pipeline(self):
        """
        Full daily pipeline:
        Monitor → Score → Generate → Publish
        """

        logger.info("Starting daily podcast pipeline")

        # 1. Monitor for new papers
        candidates = await self.monitor.run()
        logger.info(f"Found {len(candidates)} candidate papers")

        if not candidates:
            return

        # 2. Score papers
        scored = await self.scorer.score_papers(candidates)

        # 3. Filter to episode-worthy papers
        to_generate = [p for p in scored if p.should_generate]
        logger.info(f"{len(to_generate)} papers selected for episodes")

        # 4. Generate episodes (limit to top 3 per day)
        for scored_paper in to_generate[:3]:
            try:
                # Get matching subscriptions to determine style/duration
                style, duration = await self._determine_preferences(scored_paper)

                # Generate episode
                episode = await self.generator.generate_episode(
                    scored_paper=scored_paper,
                    style=style,
                    duration=duration,
                )

                # Save to database
                await self.episode_repo.create(episode)

                # Publish
                await self.publisher.publish_episode(episode)

                logger.info(
                    "Episode generated and published",
                    episode_id=episode.id,
                    paper_id=scored_paper.paper.paper_id,
                    score=scored_paper.total_score,
                )

            except Exception as e:
                logger.error(
                    "Failed to generate episode",
                    paper_id=scored_paper.paper.paper_id,
                    error=str(e)
                )

        # 5. Handle breaking news (immediate publish)
        breaking = [p for p in scored if p.is_breaking]
        for paper in breaking:
            # Trigger immediate generation task
            generate_episode_task.delay(
                paper_id=paper.paper.paper_id,
                subscription_ids=await self._get_breaking_subscribers(paper)
            )
```

---

## 6. API Endpoints

### 6.1 Router

```python
# backend/app/routers/podcast.py

from fastapi import APIRouter, Depends, HTTPException
from app.schemas.podcast import *
from app.services.podcast import PodcastService

router = APIRouter(prefix="/api/podcast", tags=["podcast"])


# ============ Subscriptions ============

@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    service: PodcastService = Depends(),
):
    """Create a new podcast subscription."""
    return await service.create_subscription(current_user.id, data)


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    current_user: User = Depends(get_current_user),
    service: PodcastService = Depends(),
):
    """List user's podcast subscriptions."""
    return await service.get_user_subscriptions(current_user.id)


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: str,
    data: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    service: PodcastService = Depends(),
):
    """Update a subscription."""
    return await service.update_subscription(subscription_id, current_user.id, data)


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    service: PodcastService = Depends(),
):
    """Delete a subscription."""
    await service.delete_subscription(subscription_id, current_user.id)
    return {"status": "deleted"}


# ============ Episodes ============

@router.get("/episodes", response_model=list[EpisodeResponse])
async def list_episodes(
    topic: str | None = None,
    domain: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: PodcastService = Depends(),
):
    """List published episodes with optional filters."""
    return await service.list_episodes(
        topic=topic,
        domain=domain,
        limit=limit,
        offset=offset,
    )


@router.get("/episodes/{episode_id}", response_model=EpisodeDetailResponse)
async def get_episode(
    episode_id: str,
    service: PodcastService = Depends(),
):
    """Get episode details including script and audio URL."""
    episode = await service.get_episode(episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    return episode


@router.get("/episodes/{episode_id}/script")
async def get_episode_script(
    episode_id: str,
    service: PodcastService = Depends(),
):
    """Get full episode script."""
    return await service.get_episode_script(episode_id)


# ============ On-Demand Generation ============

@router.post("/generate", response_model=EpisodeResponse)
async def generate_episode_on_demand(
    data: GenerateEpisodeRequest,
    current_user: User = Depends(get_current_user),
    service: PodcastService = Depends(),
):
    """
    Generate episode on-demand for a specific paper.
    (Not agentic - user-triggered)
    """
    return await service.generate_episode(
        paper_id=data.paper_id,
        style=data.style,
        duration=data.duration,
        language=data.language,
    )


# ============ RSS Feed ============

@router.get("/feed/{user_id}.xml")
async def get_rss_feed(
    user_id: str,
    service: PodcastService = Depends(),
):
    """
    Get personalized RSS feed for user's subscriptions.
    Can be added to any podcast app.
    """
    feed = await service.generate_rss_feed(user_id)
    return Response(content=feed, media_type="application/xml")


# ============ Admin / Debug ============

@router.post("/admin/trigger-pipeline")
async def trigger_pipeline(
    current_user: User = Depends(get_current_admin),
):
    """Manually trigger the daily pipeline (admin only)."""
    from app.tasks.podcast import daily_monitor_task
    daily_monitor_task.delay()
    return {"status": "triggered"}


@router.get("/admin/paper-scores")
async def get_recent_scores(
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    service: PodcastService = Depends(),
):
    """View recent paper scores for debugging."""
    return await service.get_recent_scores(limit)
```

---

## 7. Storage Structure

### 7.1 MinIO/S3 Layout

Podcast files stored in the same `oaria-papers` bucket, under `podcast/` prefix:

```
oaria-papers/                          # Existing bucket
├── canonical/                         # Existing paper storage
│   └── {paper_id}/                    # e.g., pmc_PMC12345678
│       ├── raw.xml
│       ├── fulltext.txt
│       ├── display.json
│       └── paper.pdf
└── podcast/                           # NEW: Podcast storage
    └── episodes/
        └── {episode_id}/              # UUID
            ├── audio.mp3              # Generated audio file
            └── script.json            # Episode script
```

**S3 Key Examples:**
- Audio: `podcast/episodes/550e8400-e29b-41d4-a716-446655440000/audio.mp3`
- Script: `podcast/episodes/550e8400-e29b-41d4-a716-446655440000/script.json`

**Presigned URLs:** Generated for audio playback (1 hour expiry default)

---

## 8. Configuration

### 8.1 Environment Variables

Uses existing MinIO config from docker-compose.yml:

```bash
# .env

# Podcast Feature
PODCAST_ENABLED=true
PODCAST_DAILY_RUN_HOUR=6
PODCAST_MAX_EPISODES_PER_DAY=3
PODCAST_EPISODE_THRESHOLD=60
PODCAST_BREAKING_THRESHOLD=85

# TTS Provider
TTS_PROVIDER=openai           # openai | elevenlabs | edge
TTS_OPENAI_API_KEY=sk-...
TTS_ELEVENLABS_API_KEY=...

# Storage
PODCAST_STORAGE_BUCKET=oaria-podcasts

# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
```

### 8.2 Feature Config

```python
# backend/app/config/podcast_config.py

from pydantic_settings import BaseSettings

class PodcastSettings(BaseSettings):
    enabled: bool = True

    # Scheduler
    daily_run_hour: int = 6
    max_episodes_per_day: int = 3

    # Scoring thresholds
    episode_threshold: float = 60.0
    breaking_threshold: float = 85.0

    # TTS
    tts_provider: str = "openai"  # openai, elevenlabs, edge

    # Defaults
    default_style: str = "two_hosts"
    default_duration: str = "short"
    default_language: str = "en"

    # Voices (OpenAI)
    voice_host1: str = "alloy"
    voice_host2: str = "nova"
    voice_expert: str = "onyx"
    voice_narrator: str = "nova"

    class Config:
        env_prefix = "PODCAST_"
```

---

## 9. LLM Prompts for Episode Generation

### 9.1 Script Generation Prompts

```python
# backend/app/services/podcast/prompts.py

SYSTEM_PROMPT_TWO_HOSTS = """You are a professional podcast scriptwriter.
Create engaging, accessible dialogue between two hosts discussing academic research.

Host 1 (Alex): The explainer - clearly explains the research, knowledgeable but not condescending
Host 2 (Sam): The curious one - asks smart questions, represents the listener's perspective

Guidelines:
- Natural, conversational tone (avoid reading like a paper)
- Explain jargon immediately when used
- Use relatable analogies for complex concepts
- Include moments of genuine curiosity, surprise, or excitement
- Build narrative tension (what was the problem? why does it matter?)
- End with clear takeaways for the listener
"""

SYSTEM_PROMPT_INTERVIEW = """You are a professional podcast scriptwriter.
Create an interview format where a host interviews a virtual expert about research.

Host: Asks insightful, probing questions
Expert: Provides authoritative, detailed answers with nuance

Guidelines:
- Professional but accessible tone
- Deep dive into methodology when relevant
- Address limitations honestly
- Discuss real-world implications
- Include follow-up questions that a curious listener would ask
"""

SYSTEM_PROMPT_SOLO = """You are a professional podcast scriptwriter.
Create a solo narrator script explaining research in a documentary style.

Narrator: Clear, engaging, authoritative but warm

Guidelines:
- Storytelling approach with narrative arc
- Build from problem → discovery → implications
- Use vivid, descriptive language
- Include dramatic pauses/emphasis markers
- Make the listener feel like they're on a journey of discovery
"""

EPISODE_GENERATION_PROMPT = """Create a podcast episode about this research paper.

## PAPER INFORMATION
Title: {title}
Authors: {authors}
Journal: {journal}
Publication Date: {publication_date}

## ABSTRACT
{abstract}

## KEY FINDINGS (extracted from full text)
{key_findings}

## EPISODE REQUIREMENTS
Target Length: ~{word_count} words
Style: {style}
Language: {language}

## STRUCTURE
1. Hook (15 seconds): Grab attention with the most surprising/important finding
2. Context (1 minute): Why this research matters, what problem it addresses
3. The Research (2-3 minutes): What they did and found, explained simply
4. Implications (1 minute): What this means for patients/science/society
5. Takeaway (30 seconds): The one thing listeners should remember

## OUTPUT FORMAT
Return valid JSON:
{{
    "title": "Catchy episode title (not the paper title)",
    "description": "2-3 sentence hook for episode listing",
    "dialogue": [
        {{"speaker": "host1", "name": "Alex", "text": "...", "emotion": "curious"}},
        {{"speaker": "host2", "name": "Sam", "text": "...", "emotion": "surprised"}},
        ...
    ],
    "chapters": [
        {{"time": 0, "title": "Introduction"}},
        {{"time": 60, "title": "The Research Question"}},
        ...
    ]
}}

Emotion options: neutral, curious, excited, surprised, thoughtful, emphatic
"""
```

### 9.2 Importance Scoring Prompts

```python
NOVELTY_SCORING_PROMPT = """Analyze this research paper for novelty and breakthrough potential.

Title: {title}
Abstract: {abstract}

Score from 0-25 based on:
- Does it contradict or challenge existing consensus? (high novelty)
- Does it introduce a new method, technique, or approach?
- Does it solve a previously unsolved problem?
- Is it a first-of-its-kind study (first in humans, first long-term, etc.)?

Return JSON:
{{
    "score": <0-25>,
    "reasons": ["reason 1", "reason 2"],
    "is_breakthrough": true/false
}}

Scoring guide:
- 0-5: Incremental, confirmatory study
- 6-10: Solid contribution, some novelty
- 11-15: Notable advance in the field
- 16-20: Significant breakthrough
- 21-25: Paradigm-shifting discovery (very rare)

Be strict. Most papers are incremental (score 5-10).
"""

PUBLIC_INTEREST_PROMPT = """Analyze this research for public interest potential.

Title: {title}
Abstract: {abstract}

Score from 0-25 based on:
- Would general public care about this finding?
- Does it affect daily life, health decisions, or policy?
- Is it newsworthy? Would media cover it?
- Would it trend on social media or spark conversation?

Return JSON:
{{
    "score": <0-25>,
    "reasons": ["reason 1", "reason 2"],
    "news_angle": "One-sentence news headline"
}}

Scoring guide:
- 0-5: Highly technical, niche audience only
- 6-10: Interesting to specialists and some public
- 11-15: Newsworthy, broad health/science interest
- 16-20: Major public health/policy implications
- 21-25: Paradigm shift affecting everyone (very rare)

Be realistic. Most research is niche (score 5-10).
"""
```

---

## 10. Full File Structure (Post-MVP)

```
backend/
├── app/
│   ├── routers/
│   │   └── podcast.py                 # API endpoints
│   ├── schemas/
│   │   └── podcast.py                 # Pydantic models
│   ├── models/
│   │   └── podcast.py                 # SQLAlchemy models
│   ├── services/
│   │   └── podcast/
│   │       ├── __init__.py
│   │       ├── service.py             # Main service
│   │       ├── orchestrator.py        # Pipeline coordinator
│   │       ├── agents/
│   │       │   ├── __init__.py
│   │       │   ├── monitor.py         # Paper Monitor Agent
│   │       │   ├── scorer.py          # Importance Scorer Agent
│   │       │   ├── generator.py       # Episode Generator Agent
│   │       │   └── publisher.py       # Publisher Agent
│   │       ├── tts/
│   │       │   ├── __init__.py
│   │       │   ├── base.py            # TTS interface
│   │       │   ├── openai_tts.py
│   │       │   ├── elevenlabs_tts.py
│   │       │   └── edge_tts.py        # Free option
│   │       └── prompts.py             # LLM prompts
│   ├── tasks/
│   │   └── podcast.py                 # Celery tasks
│   └── config/
│       └── podcast_config.py
├── tests/
│   └── services/
│       └── podcast/
│           ├── test_monitor.py
│           ├── test_scorer.py
│           ├── test_generator.py
│           └── test_publisher.py
```

---

## 11. Implementation Plan (3-Day MVP)

> **Epic**: OAR-117 - F-11: Agentic Podcast System

### Day 1: Foundation

| Ticket | Task | Estimate |
|--------|------|----------|
| OAR-118 | Database tables + migration | 2h |
| OAR-119 | Pydantic schemas | 1h |
| OAR-120 | TTS Service (OpenAI) | 2h |
| OAR-121 | S3 audio upload extension | 1h |

**Deliverable**: Can synthesize speech and upload to S3

### Day 2: Core Generation

| Ticket | Task | Estimate |
|--------|------|----------|
| OAR-122 | Episode Generator Agent | 3h |
| OAR-123 | LLM Prompts | 1h |
| OAR-124 | Audio generation + concatenation | 2h |
| OAR-125 | Podcast service orchestration | 2h |

**Deliverable**: Can generate complete episode from paper

### Day 3: API & Scheduling

| Ticket | Task | Estimate |
|--------|------|----------|
| OAR-126 | API endpoints | 3h |
| OAR-127 | Celery + Redis setup | 2h |
| OAR-128 | Scheduled task | 1h |
| OAR-129 | Integration test + docs | 2h |

**Deliverable**: Working MVP with scheduled generation

### Files to Create (MVP)

```
backend/app/
├── models/podcast.py              # 2 SQLAlchemy models
├── schemas/podcast.py             # Pydantic schemas
├── routers/podcast.py             # API endpoints
├── services/podcast/
│   ├── __init__.py
│   ├── service.py                 # Main service
│   ├── generator.py               # Episode generator
│   ├── tts_service.py             # OpenAI TTS
│   └── prompts.py                 # LLM prompts
├── tasks/podcast.py               # Celery tasks
└── celery_app.py                  # Celery configuration
```

### Deferred to Post-MVP

| Feature | Reason |
|---------|--------|
| Paper Monitor Agent | Use existing DB papers instead |
| Publisher Agent | Download link only, no email/RSS |
| paper_scores table | Simple selection without scoring history |
| episode_deliveries table | No delivery tracking needed for MVP |
| ElevenLabs/Edge TTS | OpenAI TTS sufficient for MVP |

---

## 12. Success Metrics

| Metric | Target |
|--------|--------|
| Episodes generated per week | >= 5 |
| Subscriber retention (30 day) | >= 70% |
| Email open rate | >= 40% |
| Listen completion rate | >= 60% |
| Paper -> Episode latency | < 24 hours |
| Audio quality score (user rating) | >= 4.0/5.0 |

---

## 13. Future Enhancements

1. **Multi-paper episodes**: Combine related papers into theme episodes
2. **Listener feedback loop**: Learn from engagement to improve scoring
3. **Voice cloning**: Custom voices for institutions
4. **Spotify/Apple integration**: Direct publishing to platforms
5. **Interactive transcripts**: Clickable citations in transcript
6. **Multi-language**: Auto-translate episodes to Korean, Chinese, etc.

---

*Last updated: 2025-01-19*
