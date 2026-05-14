# RabbitPedia

**Go down rabbit holes — intelligently.**

RabbitPedia transforms Wikipedia research into a living, conversational experience. Instead of passively reading dense encyclopaedia articles, you search a topic and receive a structured, AI-synthesised response: key concepts, interesting facts, an opinionated commentary, and clickable threads to follow wherever your curiosity leads. Every page you visit is remembered. Every interest you flag shapes what comes next.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Technology Stack](#technology-stack)
- [Architecture Overview](#architecture-overview)
- [Wikipedia Data Extraction](#wikipedia-data-extraction)
- [Session & Persistence Layer](#session--persistence-layer)
- [AI Pipeline](#ai-pipeline)
  - [Home Page — Research & Chat](#home-page--research--chat)
  - [Knowledge Graph Page](#knowledge-graph-page)
  - [Debate Page](#debate-page)
  - [Perspectives Page](#perspectives-page)
  - [Curiosity Path Page](#curiosity-path-page)
  - [Connection Explainer](#connection-explainer)
- [UI & Data Presentation](#ui--data-presentation)
- [Knowledge Graph Visualisation](#knowledge-graph-visualisation)
- [Curiosity Path Visualisation](#curiosity-path-visualisation)
- [Streaming Protocol](#streaming-protocol)
- [Personalisation & Interest Tracking](#personalisation--interest-tracking)
- [Observability](#observability)
- [Running Locally](#running-locally)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)

---

## What It Does

Wikipedia has ~60 million articles. Reading them is passive, slow, and lonely. RabbitPedia fixes this by sitting between you and Wikipedia and acting as a knowledgeable, opinionated research companion:

| Feature | What it gives you |
|---|---|
| **Chat & Synthesis** | Wikipedia content rewritten into structured, readable sections with AI commentary |
| **Deep Mode** | Multi-article synthesis that cross-references three related Wikipedia pages |
| **Knowledge Graph** | A live D3 force graph showing how your search topic connects to its Wikipedia neighbours |
| **Debate Mode** | Two AI narrators argue opposing sides of a controversial topic using real Wikipedia excerpts |
| **Perspectives** | Four historically/culturally distinct narrators retell the same topic in first-person voice |
| **Curiosity Path** | A visualised map of every topic you've explored, with AI insight about your research pattern |
| **Session Memory** | Every conversation, interest flag, and personal fact persists for 24 hours via Redis |

---

## Technology Stack

### Backend

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Web framework | FastAPI 0.115 (async, ASGI) |
| ASGI server | Uvicorn with standard extras |
| LLM orchestration | LangChain 0.3 + LangChain-Groq 0.3 |
| Inference provider | Groq API |
| Primary model | `llama-3.3-70b-versatile` |
| Fast / lightweight model | `llama-3.1-8b-instant` |
| Structured output | LangChain `with_structured_output()` via Groq function calling |
| Wikipedia access | `wikipediaapi` 0.8 + `httpx` 0.28 (MediaWiki Action API) |
| Session store | Redis 5+ via `redis.asyncio` |
| Config | `python-dotenv` |
| Testing | `pytest` + `pytest-asyncio` |

### Frontend

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router, React 19) |
| State management | Zustand 5 (with localStorage persistence) |
| Visualisation | D3.js 7 (force simulation, node-link diagrams) |
| Styling | Tailwind CSS 4 + plain CSS (Wikipedia-faithful design language) |
| PDF export | `html2canvas` + `jsPDF` |
| Language | TypeScript 5 |

### Transport

- All AI-generated responses are streamed over **Server-Sent Events (SSE)** from FastAPI to Next.js.
- Non-streaming endpoints (graph, perspectives, path) return plain JSON.
- CORS is configured for `localhost:3000 ↔ localhost:8000` in development.

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│                  Browser                    │
│  Next.js 16 App Router (port 3000)          │
│                                             │
│  /          Home chat + sidebar trail       │
│  /graph     D3 knowledge graph              │
│  /debate    Staged debate arguments         │
│  /perspectives  4-narrator lens flip        │
│  /curiosity-path  Journey visualisation     │
└───────────────┬─────────────────────────────┘
                │  SSE / JSON  (HTTP)
┌───────────────▼─────────────────────────────┐
│           FastAPI Backend (port 8000)        │
│                                             │
│  POST /chat          → SSE stream           │
│  GET  /graph         → JSON                 │
│  GET  /debate        → SSE NDJSON stream    │
│  POST /debate/challenge → JSON              │
│  GET  /perspective   → JSON                 │
│  GET  /path          → JSON                 │
│  GET  /connection    → JSON                 │
│  POST /interest      → 200 OK               │
│  POST /feedback      → 200 OK               │
└──────┬────────────────────┬─────────────────┘
       │                    │
┌──────▼──────┐    ┌────────▼────────┐
│  Groq API   │    │   Wikipedia     │
│  (LLMs)     │    │   MediaWiki     │
│             │    │   REST API      │
└─────────────┘    └─────────────────┘
       │
┌──────▼──────┐
│  Redis      │
│  (sessions) │
└─────────────┘
```

Each request to `/chat` runs a small pipeline:

1. **Normalise** the query into a proper Wikipedia article title
2. **Classify intent** — new research topic vs. conversational follow-up
3. **Fetch** one or more Wikipedia articles (sync, run in thread pool)
4. **Format** a structured response via LLM function calling
5. **Stream** the result back over SSE
6. **Persist** message pair to Redis; extract user facts in the background

---

## Wikipedia Data Extraction

All article data comes directly from Wikipedia — nothing is fabricated or stored locally.

### `WikipediaFetcher` (`backend/app/wikipedia_fetcher.py`)

This is the only module that talks to Wikipedia. It wraps two APIs:

- **`wikipediaapi`** — the Python library for summary, section text, and page links
- **MediaWiki Action API** via `httpx` — used for thumbnail images and `opensearch` fallback lookups

#### `search(query) → Article`

The standard lookup used on every chat request:

1. Calls `wikipediaapi.Wikipedia.page(query)` directly.
2. If the page does not exist, falls back to the MediaWiki `opensearch` endpoint to handle typos, redirects, and colloquial queries ("why did rome fall" → "Fall of the Western Roman Empire").
3. Fetches the article's **lead thumbnail** via the `pageimages` Action API at 300 px width.
4. Collects up to 10 **See Also** links from the page's internal link list.
5. Returns an `Article` TypedDict: `title`, `summary`, `url`, `see_also`, `image_url`.

The `url` field is always the canonical `page.fullurl` from Wikipedia — never synthesised or guessed. The LLM is explicitly forbidden from inventing URLs in the system prompt.

#### `deep_search(query, max_articles=3) → list[Article]`

Triggered by the "Go Deeper" button or the `?deep=true` query parameter:

1. Fetches the primary article via `search()`.
2. Runs suffix-based supplementary searches: `"{query} history"`, `"{query} impact"`.
3. Also pulls two related topics from the primary article's `see_also` list and fetches them.
4. Returns up to three distinct articles.

The response formatter is then prompted to produce a visibly richer answer — at least four body paragraphs, four or more key concepts, and source citations for every article.

#### Other methods

| Method | Purpose |
|---|---|
| `get_full_text(title)` | Fetches the complete plaintext of an article (used by Debate and Perspectives) |
| `extract_controversy_paragraphs(text)` | Scans for keywords like "controversy", "criticized", "disputed", "failed" to surface debate fodder (max 12 paragraphs) |
| `get_links(title, limit=40)` | Returns a list of up to 40 Wikipedia page titles that the article links to (used for Knowledge Graph) |

Because the Wikipedia Python library is synchronous, all calls are wrapped in `asyncio.run_in_executor` to avoid blocking FastAPI's event loop.

---

## Session & Persistence Layer

### `SessionStore` (`backend/app/session_store.py`)

An async Redis client (`redis.asyncio`) that owns all session I/O. Session IDs are UUID v4 values, generated client-side on first visit and stored in `localStorage`. The same ID is sent with every request.

#### Key structure

```
session:{id}:messages     List    Max 20 items (10 user/AI pairs, LTRIM enforced)
session:{id}:interests    Sorted Set   {tag: score}  — score incremented per "Interested" click
session:{id}:user_facts   Hash    {profession, interests, location, expertise_level, other}
session:{id}:meta         Hash    {created_at, last_active, expiry_warned}
session:{id}:feedback     Hash    {message_id: "up" | "down"}
```

All keys share a 24-hour TTL, refreshed on every `add_message_pair()` call.

#### Expiry warning

When a session's TTL drops below two hours, the backend sets `meta.expiry_warned = "1"` and returns `session_expiry_warning: true` inside the SSE `done` event. The frontend shows a dismissable yellow banner — exactly once per session.

#### Graceful degradation

Every Redis operation is wrapped in a try/except. If Redis is unavailable, the application continues serving requests — it just loses session persistence.

---

## AI Pipeline

### Home Page — Research & Chat

**Endpoint:** `POST /chat`

The chat endpoint is the core of the product. Each request passes through up to five sequential AI steps, plus one background task.

#### Step 1 — Query Normalisation (`query_normaliser.py`)

Uses `llama-3.1-8b-instant` with `max_tokens=30` to convert a natural-language query into a Wikipedia article title. This improves lookup success significantly:

```
"why did the roman empire fall"  →  "Fall of the Western Roman Empire"
"how does wifi work"             →  "Wi-Fi"
"black holes explained"          →  "Black hole"
```

Only runs when intent is classified as `research` (step 2 runs first for sessions with history).

#### Step 2 — Intent Classification (`router.py`)

Uses `llama-3.1-8b-instant` with `max_tokens=50`. For the first message in a session the intent is always `research`. For subsequent messages it classifies:

- **`research`** — the user wants to explore a new topic; triggers Wikipedia fetch + full formatting pipeline
- **`conversational`** — the user is chatting about something already discussed; triggers a lightweight prose reply with no Wikipedia fetch

#### Step 3 — Wikipedia Fetch

`WikipediaFetcher.search()` or `.deep_search()` runs in a thread pool. The result — one or three `Article` objects — is passed into the formatter.

#### Step 4 — Response Formatting (`response_formatter.py`)

This is the main generative step. Uses `llama-3.3-70b-versatile` with `max_tokens=3000` and LangChain's `with_structured_output()` to guarantee the response matches the `ResponseSection` Pydantic schema via Groq function calling:

```python
class ResponseSection(BaseModel):
    heading: str
    body: str                          # 2-4 paragraphs, split on \n\n
    key_concepts: list[KeyConcept] | None
    did_you_know: list[str]            # 2-3 facts
    two_cents: str                     # AI's opinionated commentary
    sources: list[str]                 # Wikipedia URLs only
    explore_further: ExploreFurther    # from_article + suggestions
```

The system prompt enforces several invariants:
- Never invent, guess, or fabricate any Wikipedia URLs
- Cite sources from the provided article URLs only
- Write for curious, intelligent non-experts
- Maintain a warm, slightly opinionated voice ("RabbitPedia")

**Personalisation injection** (when available):

```
User has shown interest in: physics, history, space exploration
Known about user — profession: software engineer, expertise_level: advanced
```

Up to 5 interest tags and 8 extracted user facts are prepended to the system prompt. Facts already covered in recent responses are not repeated verbatim.

**History injection** (sessions with prior messages):

The last 5 user/assistant pairs are formatted as a trailing system message to give the model conversational context without interfering with the structured output contract.

**Deep mode hint** (when `?deep=true` or three articles supplied):

An additional instruction block tells the model to produce at least four body paragraphs covering distinct facets of the topic, four or more key concepts, and source citations referencing every supplied article.

#### Step 5 — Conversational Reply (`router.py`)

When intent is `conversational`, `ConversationalReplier` replaces the full pipeline. It uses `llama-3.3-70b-versatile` with `max_tokens=300` and a stripped-down system prompt:

> "You are RabbitPedia. Reply naturally and conversationally — 1–3 sentences. Stay in character: curious, opinionated, knowledgeable. Do NOT structure the reply as an article. Do NOT cite sources. Just talk."

No Wikipedia fetch. No structured output. The reply streams directly over SSE.

#### Background — Fact Extraction (`fact_extractor.py`)

Runs concurrently via `asyncio.create_task` — never blocks the main response. Uses `llama-3.1-8b-instant` with `max_tokens=200` to extract personal facts from the latest user message:

- `profession`, `interests`, `location`, `expertise_level`, `other`

Only fills a field when the user **explicitly stated** it ("I'm a doctor", "I study medieval history"). Extracted facts are stored in `session:{id}:user_facts` and injected into all future formatter prompts.

---

### Knowledge Graph Page

**Endpoint:** `GET /graph?query=...`

**No LLM inference.** The graph is built entirely from Wikipedia's own link structure.

`GraphBuilder.build()` in `backend/app/graph_builder.py`:

1. Fetches the article summary and up to 40 linked page titles via `WikipediaFetcher.get_links()`.
2. Fires concurrent `httpx` requests to fetch summaries for every neighbour.
3. Fires a second wave of concurrent requests to fetch *each neighbour's own links*, looking for cross-connections.
4. Builds edges:
   - **Origin → Neighbour** for every linked page
   - **Neighbour A → Neighbour B** if B appears in A's link list (deduplicated by sorted pair)
5. Returns `GraphData`: `nodes`, `edges`, `origin`.

The result is cached in Zustand with a 24-hour TTL so revisiting the same topic doesn't re-fetch.

---

### Debate Page

**Endpoint:** `GET /debate?query=...` (SSE stream)  
**Challenge endpoint:** `POST /debate/challenge`

The debate feature stages two AI narrators — **Red** (contrarian/minority view) and **Blue** (mainstream/expert consensus) — arguing a controversial topic using real Wikipedia content as their evidence base.

#### Research context building

Before any LLM call, `build_research_context()` in `debate_builder.py`:

1. Fetches the full article text via `get_full_text()`.
2. Extracts controversy paragraphs by scanning for keywords: "controversy", "criticized", "disputed", "failed", "alleged", "accused".
3. Fetches summaries of 8 related Wikipedia articles.
4. Concatenates into a context block:
   ```
   === CONTROVERSY EXCERPTS ===
   [real Wikipedia paragraphs]

   === RELATED TOPICS ===
   [related article summaries]
   ```

#### Debate meta construction

`DebateBuilder.build_meta()` uses `llama-3.3-70b-versatile` to produce a `DebateMeta` object:

- `topic` — the article title
- `question` — the central debatable question
- `context` — neutral background in 2-3 sentences
- `red` — contrarian position summary
- `blue` — mainstream position summary
- `verdict` — what academic consensus actually says (neutral; no winner declared)

The system prompt instructs the model to ground everything in the controversy excerpts and never fabricate claims.

#### Streaming debate rounds

`DebateBuilder.stream_rounds()` generates 14 rounds: 7 for Red, 7 for Blue. Both sides use `llama-3.3-70b-versatile`. The round types, in order:

```
opening → argument → argument → rebuttal → argument → rebuttal → closing
```

Each round is a `DebateArgument`:

```python
class DebateArgument(BaseModel):
    side_id: Literal["red", "blue"]
    type: str          # "opening", "argument", "rebuttal", "closing"
    heading: str       # 4-8 words
    content: str       # 2-3 assertive sentences
    targets: str       # which specific claim this contests
    sources: list[str] # exact Wikipedia article titles cited
```

Rounds are streamed as **NDJSON** (one JSON object per line) over SSE. A custom parser on the backend handles streaming JSON tokens, markdown code fences, trailing commas, and incomplete objects before yielding validated `DebateArgument` instances.

#### Challenge responses

Users can submit a challenge to either side mid-debate. The backend fetches both current positions from the request body and prompts the model to generate one rebuttal per side, returning a `ChallengeReply` with `red_reply` and `blue_reply`.

---

### Perspectives Page

**Endpoint:** `GET /perspective?query=...`

`PerspectiveBuilder.build()` uses `llama-3.3-70b-versatile` with `max_tokens=5000` to generate exactly four distinct first-person perspectives on the same topic.

#### Narrator selection rules (in the system prompt)

The model is instructed to:
- Pick narrators who **genuinely disagree**, not just use different language
- Include a **non-Western cultural** perspective
- Include a perspective from a **different historical era**
- Include someone who **lost or was opposed** to the thing being described
- Include a **modern expert or descendant** directly affected by it

#### Per-narrator output

Each `PerspectiveSection` contains:

```python
class PerspectiveSection(BaseModel):
    narrator_name: str
    narrator_description: str    # who they are, in 1-2 sentences
    stance: str                  # their relationship to the topic
    color: str                   # "red" | "blue" | "purple" | "green" | "orange"
    title: str                   # their headline for the topic
    body: str                    # 3-4 paragraphs in first-person voice
    what_they_omit: str          # blind spots they'd ignore
    most_revealing_line: str     # single sentence pulled exactly from body
    emphasis: str                # what they'd foreground
```

Body text is written in the narrator's authentic vocabulary and value system — a Roman senator sounds nothing like a 21st-century climate scientist. Results are cached client-side for 24 hours.

---

### Curiosity Path Page

**Endpoint:** `GET /path?session_id=...`

`PathAnalyzer.analyze()` uses `llama-3.3-70b-versatile` with `max_tokens=4000` and `temperature=0.7` to produce a "curiosity cartography" — an annotated map of the user's intellectual journey through their session.

#### Input

- Full session history (all topics explored, in order)
- User interest tags (from Redis sorted set)
- Session metadata (creation time, duration)

#### Output

```python
class PathData(BaseModel):
    nodes: list[PathNode]    # one per topic explored
    edges: list[PathEdge]    # consecutive + thematic connections
    insight: CuriosityInsight
    total_topics: int
    session_duration_minutes: float
```

Each `PathNode` includes:
- `order` — when it was explored
- `summary` — what the topic is
- `why_interesting` — why *this specific user*, given their context, found it interesting

`CuriosityInsight` includes:
- `theme` — the overarching thread connecting the topics
- `most_unexpected_jump` — the most surprising topic transition
- `rabbit_hole_depth` — one of: `surface skimmer`, `focused diver`, `wide wanderer`, `deep obsessive`
- `next_recommendation` — where to go next

The system prompt asks for a warm, slightly poetic tone — think of it as a letter from a librarian who watched you work.

The endpoint requires a minimum of 3 topics and at least one message pair to produce a meaningful path. The frontend shows a placeholder if the session is too short.

---

### Connection Explainer

**Endpoint:** `GET /connection?node=...&origin=...`

Triggered when a user clicks a node on the Knowledge Graph.

`connection_router.get_connection()`:

1. Fetches both articles and their full texts.
2. Searches each article for paragraphs that mention the other topic.
3. Extracts up to 4 such paragraphs per direction.
4. Passes all excerpts to `llama-3.3-70b-versatile` with `temperature=0.6` and `max_tokens=800`.

The system prompt tells the model to ground its explanation in the specific excerpts — not to invent connections — and to write for curious, non-expert readers. Returns a `ConnectionData` with a heading, body, and URLs for both articles.

---

## UI & Data Presentation

### Home Page

The home page mirrors Wikipedia's visual language — a clean serif reading environment — but adds interactive layers.

**Search bar** (top of page, initial focus):
- Accepts natural language, questions, or article titles
- Enter or the Search button triggers a `/chat` request

**Wiki section** (the main content area, rendered by `ChatPanel`):

Each AI response is rendered as a structured section containing:

| Element | What it shows |
|---|---|
| **Heading** | The synthesised article title |
| **Infobox** | Wikipedia thumbnail (left-floated, matching Wikipedia's own layout) |
| **Body** | 2–4 paragraphs of AI synthesis, sourced from Wikipedia |
| **Key Concepts** | Term → definition list (rendered as a glossary table) |
| **Did You Know?** | 2–3 facts with "Interested" / "Not interested" toggle buttons |
| **RabbitPedia's Two Cents** | The AI's opinionated take — what's underrated, surprising, or contested about this topic |
| **Sources** | Linked canonical Wikipedia URLs |
| **Explore Further** | "From this article" (See Also links) + "You might like" (AI suggestions) |
| **Feedback** | Thumbs up / thumbs down (stored for evaluation) |

**Sidebar** (the Rabbit Hole trail):
- Numbered list of every topic explored this session
- Child topics (followed from suggestion chips) are indented under their parent
- Clicking any item smooth-scrolls to that section on the page
- Collapsible with a slide animation; on mobile it becomes a fixed left drawer

**Bottom input bar** (fixed, always visible):
- Textarea that grows with multi-line input
- Both research queries and conversational messages are accepted

**Discovery panel** (shown when the session has no messages yet):
- Fetches today's Wikipedia Featured Article from the MediaWiki REST API
- Shows as a prompt to begin exploring

### Navigation bar (shared across all pages)

Links to all five pages. The active route is highlighted. Dark mode toggle is in the top-right.

---

## Knowledge Graph Visualisation

The Knowledge Graph page (`/graph`) shows how a topic connects to its Wikipedia neighbourhood.

### D3 force simulation

The graph uses a `d3.forceSimulation` with:
- `forceLink` — pulls connected nodes together
- `forceManyBody` — mutual repulsion to spread nodes apart
- `forceCenter` — anchors the layout to the viewport centre

**Nodes:**
- Gold fill: the origin topic (your search)
- Blue fill: every connected Wikipedia article
- Radius scales with number of connections

**Edges:**
- Grey lines with arrowhead markers
- Labelled with "links to" (or the edge label returned by the backend)

**Interactions:**
- **Hover** — shows the article's first-sentence summary in a tooltip
- **Click** — selects the node; triggers a `/connection` request that explains the relationship between this node and the origin in the right-hand ChatPanel
- **Pulse animation** — when a node topic is mentioned in the chat, the corresponding node pulses gold

**Resizable panels:**
- Left sidebar: history of all topics you've graphed this session (click to re-render)
- Right panel: the ChatPanel, which explains connections and answers follow-up questions

---

## Curiosity Path Visualisation

The Curiosity Path page (`/curiosity-path`) renders your session's topic history as a node-link diagram.

### D3 node-link layout

`CuriosityPathGraph` (`frontend/components/CuriosityPathGraph.tsx`) uses a `d3.forceSimulation`:
- Each node is a topic you explored
- Consecutive topics are connected by edges
- Thematic connections (when the AI detects non-obvious links) add additional edges

Node colour encodes curiosity depth or the order of exploration (configurable via the colour scale). Node size encodes how many connections that topic has.

**Interactions:**
- Click a node to see its `why_interesting` annotation in the right sidebar
- "Share as Image" exports the full graph as a PNG via `html2canvas`

**Insight panel** (`CuriosityInsightPanel`):
- Shows `theme`, `rabbit_hole_depth`, `most_unexpected_jump`, and `next_recommendation`
- Appears in the right sidebar next to the graph

---

## Streaming Protocol

Every SSE response follows a three-event protocol:

```
event: message
data: {"type": "thinking"}

event: message
data: {"type": "section", "content": { ...ResponseSection fields... }}

event: message
data: {"type": "done", "content": {"total_ms": 1842, "session_expiry_warning": false}}
```

`thinking` is emitted immediately so the frontend can show a loading indicator. `section` carries the full structured response. `done` carries timing metrics and the expiry warning flag.

The frontend (`ChatPanel.tsx`) maintains a `loadingRef` that prevents a second request from firing while one is in flight — one in-flight request per session is enforced.

For the Debate page, rounds stream as **NDJSON** (newline-delimited JSON):

```
data: {"type": "meta", "content": {...DebateMeta...}}
data: {"type": "round", "content": {...DebateArgument...}}
... (×14 rounds)
data: {"type": "done"}
```

---

## Personalisation & Interest Tracking

### Interest tags

Every "Did You Know?" fact has "Interested" and "Not interested" buttons. When a user clicks "Interested":

1. The frontend sends `POST /interest` with `{ session_id, fact, interested: true }`.
2. The backend calls `SessionStore.add_interest(session_id, tag)` which increments the tag's score in `session:{id}:interests`.
3. On the next `/chat` request, the top 5 interest tags are fetched and injected into the formatter's system prompt:
   ```
   User has shown interest in: space exploration, quantum physics, Roman history
   ```

This biases the AI's "You might like" suggestions and subtly shapes how it frames subsequent responses.

### User fact extraction

Every user message is processed in the background by `FactExtractor`. When the user says "I'm a software engineer studying distributed systems", the model extracts:

```json
{
  "profession": "software engineer",
  "interests": "distributed systems"
}
```

These facts are stored in `session:{id}:user_facts` and injected into future prompts:

```
Known about user — profession: software engineer, interests: distributed systems
```

Facts are only extracted from explicit statements — the model does not infer or guess.

---

## Observability

`observability.py` provides structured logging at every meaningful step in the pipeline:

- `wikipedia_fetch` — article title, source, duration
- `agent_invoke` — model name, token usage
- `format` — structured output shape, token count
- `stream` — bytes sent, total duration

Every endpoint logs a `total_ms` timing. The `/chat` endpoint returns `total_ms` in the SSE `done` event so the frontend can display latency.

User feedback (`POST /feedback`) stores thumbs up/down ratings in `session:{id}:feedback` for offline evaluation. Interest tracking provides an implicit signal about which topics engaged users.

Rate limiting is applied to all LLM-calling endpoints to protect against runaway Groq API costs. Token counts are capped per request and never left to user-controlled input.

---

## Running Locally

### Prerequisites

- Python 3.13+
- Node.js 18+
- Redis (local or Docker)
- A [Groq API key](https://console.groq.com)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env        # fill in GROQ_CLIENT_ID and REDIS_URL
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                    # starts on http://localhost:3000
```

### Redis (Docker)

```bash
docker run -p 6379:6379 redis:7
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_CLIENT_ID` | Yes | Groq API key |
| `REDIS_URL` | No | Redis connection string (default: `redis://localhost:6379`) |

---

## Project Structure

```
rabbit-pedia/
├── backend/
│   └── app/
│       ├── main.py                 FastAPI app + /chat, /interest, /feedback endpoints
│       ├── wikipedia_fetcher.py    Wikipedia API integration (search, deep_search, get_links)
│       ├── response_formatter.py   Structured LLM output (ResponseSection Pydantic model)
│       ├── session_store.py        Async Redis client (messages, interests, user_facts)
│       ├── router.py               Intent classification + conversational replies
│       ├── query_normaliser.py     Convert natural-language queries to article titles
│       ├── fact_extractor.py       Background user fact extraction
│       ├── graph_builder.py        D3 knowledge graph construction from Wikipedia links
│       ├── graph_router.py         GET /graph endpoint
│       ├── debate_builder.py       Controversy context + streaming debate rounds
│       ├── debate_router.py        GET /debate + POST /debate/challenge endpoints
│       ├── perspective_builder.py  4-narrator first-person perspective generation
│       ├── perspective_router.py   GET /perspective endpoint
│       ├── path_analyzer.py        Curiosity journey analysis
│       ├── path_router.py          GET /path endpoint
│       ├── connection_router.py    GET /connection endpoint
│       ├── llm_client.py           Centralised Groq client factory
│       ├── observability.py        Structured logging + phase timers
│       └── history_parser.py       Session history formatting for LLM context
│
├── frontend/
│   └── app/
│       ├── page.tsx                Home chat interface + sidebar trail
│       ├── graph/page.tsx          D3 knowledge graph page
│       ├── debate/page.tsx         Debate UI + argument cards + challenge input
│       ├── perspectives/page.tsx   4-narrator perspective cards
│       ├── curiosity-path/page.tsx Curiosity path D3 graph + insight panel
│       ├── layout.tsx              Root layout + nav
│       └── globals.css             Wikipedia-faithful global styles
│   └── components/
│       ├── ChatPanel.tsx           Shared SSE handler + section rendering
│       ├── CuriosityPathGraph.tsx  D3 path visualisation
│       ├── CuriosityInsightPanel.tsx  Insight metadata display
│       └── ThemeProvider.tsx       Dark mode context
│   └── store/index.ts              Zustand state (session, dark mode, 24hr caches)
│
├── context/
│   ├── CONTEXT.md                  Domain glossary + invariants + tech stack
│   ├── KNOWLEDGE_GRAPH.md          Graph feature spec
│   ├── DEBATE_MODE.md              Debate feature spec
│   └── CURIOSITY_PATH.md           Curiosity path feature spec
│
├── .env                            Secrets (never committed)
└── implementation-plan.md          Phased execution plan (10 slices)
```
