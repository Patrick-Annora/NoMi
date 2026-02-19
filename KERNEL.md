# KERNEL.md — Cortex: Local-First AI Brain Dump System

> A comprehensive product specification for a local-first personal knowledge capture and retrieval system. Notes go in fast, metadata gets auto-extracted by a local model, and an AI agent lets you search and synthesize across everything you've ever written. Detailed enough for Claude Code to implement without further clarification.

---

## 1. PRODUCT OVERVIEW

### 1.1 Vision
A personal second brain that gets out of the way on input and becomes brilliant on output. Write notes as fast as you think — from a CLI one-liner or a quick web form — and a local AI silently tags, timestamps, embeds, and organizes everything behind the scenes. When you need something back, ask in natural language and an AI agent searches, retrieves, and synthesizes across your entire knowledge base.

This is NOT Notion. This is NOT Obsidian. This is a personal knowledge pipe: text in, intelligence out.

### 1.2 Core Philosophy
- **Zero-friction capture**: Writing a note should be faster than opening an app. CLI-first, no mandatory fields, no templates, no folder decisions.
- **AI does the organizing**: You never manually tag, categorize, or file anything. A local model extracts metadata on every write — topics, categories, entities, sentiment — and stores it alongside the raw text.
- **Search by asking**: Retrieval is conversational. "What was that pricing idea I had last week?" not `grep -r "pricing"`.
- **Local-first, cloud-optional**: All data lives on your machine in SQLite. The local model handles tagging and basic search. Claude API is available as an optional "big brain" for deeper synthesis — but the system works fully offline.
- **Single user, zero ceremony**: No auth flows, no onboarding, no multi-tenancy. This is Patrick's brain extension.

### 1.3 Target User
Single user (Patrick). CEO of Annora AI — brain moves fast, context-switches constantly between fundraising, technical decisions, customer conversations, personal development, and strategy. Needs a system that captures everything without slowing him down and surfaces it when needed.

### 1.4 Name
**Cortex** — the outer layer of the brain responsible for thought, memory, and consciousness. Your external cortex.

---

## 2. TECH STACK

### 2.1 Backend / Core
- **Language**: Python 3.12+
- **Web Framework**: FastAPI (async, fast, modern)
- **Database**: SQLite + sqlite-vec extension (vector search in the same DB as your data)
- **Templating**: Jinja2 (server-rendered, no JS build step)
- **Interactivity**: HTMX (partial page updates, SPA-like feel, zero JS framework overhead)
- **Styling**: Tailwind CSS (via CDN or standalone CLI binary — no Node required)
- **CLI**: Typer (Click-based, clean CLI framework)

### 2.2 AI Layer
- **Local Model (tagging + basic Q&A)**: Ollama running Llama 3.2 3B (or Phi-3 Mini as fallback — fast, good at structured extraction)
- **Embeddings**: sentence-transformers `all-MiniLM-L6-v2` (384-dim, fast, runs on CPU, ~80MB model)
- **Deep Q&A (optional)**: Anthropic Claude API (`claude-sonnet-4-5-20250929`) via `anthropic` Python SDK — for synthesis, multi-note analysis, and complex questions
- **Embedding on write**: Every note gets embedded on save. Stored in sqlite-vec for instant semantic search.
- **Tagging on write**: Local model extracts tags, category, entities, and a one-line summary on every save. Async — doesn't block the note capture.

### 2.3 Infrastructure
- **Runs on**: Local machine (macOS or Linux)
- **Process Manager**: Single FastAPI process (uvicorn) — launched via CLI command `cortex serve`
- **No Docker required** (but Dockerfile provided for portability)
- **No cloud services required** (Supabase, Vercel, etc.) — fully self-contained
- **Optional**: Anthropic API key in `.env` for Claude-powered deep search

### 2.4 Dev Tooling
- **Package Manager**: uv (fast Python package manager, replaces pip + venv)
- **Linting**: Ruff (fast, replaces flake8 + isort + black)
- **Type Checking**: Pyright (strict mode)
- **Task Runner**: just (justfile) or Makefile for common commands
- **Pre-commit**: ruff format + ruff check

---

## 3. DATA MODEL (SQLite)

### 3.1 Core Tables

```sql
-- Notes: the atomic unit of everything
CREATE TABLE notes (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),  -- 32-char hex ID
  raw_text TEXT NOT NULL,                                      -- exactly what you typed
  summary TEXT,                                                -- AI-generated one-line summary
  category TEXT,                                               -- AI-assigned: 'business', 'personal', 'idea', 'journal', 'meeting', 'task', 'reference'
  sentiment TEXT,                                              -- AI-assessed: 'positive', 'negative', 'neutral', 'mixed'
  source TEXT DEFAULT 'cli',                                   -- 'cli', 'web', 'api', 'whatsapp' (future)
  is_journal BOOLEAN DEFAULT 0,                                -- flag for longer journal-style entries
  word_count INTEGER,
  created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
  updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

-- Tags: extracted by the local model, many-to-many with notes
CREATE TABLE tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,                                   -- lowercase, normalized
  tag_group TEXT,                                              -- 'topic', 'entity', 'project', 'person', 'location'
  usage_count INTEGER DEFAULT 1,
  first_seen TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE TABLE note_tags (
  note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
  tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
  confidence REAL DEFAULT 1.0,                                 -- model's confidence in the tag assignment (0-1)
  PRIMARY KEY (note_id, tag_id)
);

-- Embeddings: stored via sqlite-vec virtual table
-- sqlite-vec creates this, but conceptually:
CREATE VIRTUAL TABLE note_embeddings USING vec0(
  note_id TEXT PRIMARY KEY,
  embedding FLOAT[384]                                         -- all-MiniLM-L6-v2 dimension
);

-- Search history: track what you've asked (useful for the agent)
CREATE TABLE search_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query_text TEXT NOT NULL,
  query_type TEXT DEFAULT 'semantic',                          -- 'semantic', 'keyword', 'agent'
  results_count INTEGER,
  model_used TEXT,                                             -- 'local', 'claude'
  created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

-- Collections: optional manual grouping (light structure when you want it)
CREATE TABLE collections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE TABLE note_collections (
  note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
  collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
  PRIMARY KEY (note_id, collection_id)
);
```

### 3.2 Indexes

```sql
CREATE INDEX idx_notes_created ON notes(created_at);
CREATE INDEX idx_notes_category ON notes(category);
CREATE INDEX idx_notes_source ON notes(source);
CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_group ON tags(tag_group);
CREATE INDEX idx_note_tags_note ON note_tags(note_id);
CREATE INDEX idx_note_tags_tag ON note_tags(tag_id);
```

### 3.3 Full-Text Search (FTS5)

```sql
-- SQLite FTS5 for fast keyword search alongside semantic search
CREATE VIRTUAL TABLE notes_fts USING fts5(
  raw_text,
  summary,
  content='notes',
  content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(rowid, raw_text, summary)
  VALUES (new.rowid, new.raw_text, new.summary);
END;

CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts, rowid, raw_text, summary)
  VALUES ('delete', old.rowid, old.raw_text, old.summary);
END;

CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts, rowid, raw_text, summary)
  VALUES ('delete', old.rowid, old.raw_text, old.summary);
  INSERT INTO notes_fts(rowid, raw_text, summary)
  VALUES (new.rowid, new.raw_text, new.summary);
END;
```

### 3.4 Data Volume Estimates
- 5-15 notes/day x 365 days = ~2,000-5,500 notes/year
- Average note: ~100-500 words -> ~200-1000 chars
- Embedding per note: 384 floats x 4 bytes = ~1.5KB
- Total DB size after 1 year: < 50MB including embeddings
- **This is tiny.** SQLite handles this effortlessly. No need for Postgres, no need for a vector DB.

---

## 4. FEATURE SPECIFICATIONS

### 4.0 System Architecture Overview

```
+---------------+     +---------------+
|   CLI         |     |  Web UI       |
|  (Typer)      |     | (HTMX/Jinja) |
+-------+-------+     +-------+------+
        |                      |
        +----------+-----------+
                   |
            +------v------+
            |   FastAPI    |
            |   Server     |
            +------+-------+
                   |
       +-----------+-----------+
       |           |           |
+------v--+ +-----v--+ +------v-----+
| SQLite   | | Ollama | |  Claude    |
| + vec    | | (local)| |  API (opt) |
| + FTS5   | |        | |            |
+----------+ +--------+ +------------+
```

Two interfaces (CLI + Web) hit the same FastAPI backend. The backend talks to SQLite for storage, Ollama for local AI (tagging + basic search), and optionally Claude for deep Q&A.

---

### 4.1 CLI — Quick Capture

The primary input method. Must be faster than opening any app.

#### 4.1.1 Core Commands

```bash
# Capture a note (the main action)
cortex add "Met with investor from Sequoia. They want to see 3 months of revenue data before committing. Follow up with Wes on dashboard."

# Capture from stdin (pipe support)
echo "Random thought about pricing tiers" | cortex add

# Multi-line note (opens $EDITOR or inline with heredoc)
cortex add --long
# Opens vim/nano/whatever $EDITOR is set to

# Journal entry (auto-tagged as journal, longer form)
cortex journal
# Opens $EDITOR for a longer write session

# Quick search
cortex search "what did I note about Sequoia?"

# Recent notes
cortex recent              # last 10 notes
cortex recent --today      # today's notes
cortex recent -n 20        # last 20

# Start the web server
cortex serve               # default: http://localhost:8833
cortex serve --port 9000

# Status
cortex status              # note count, DB size, Ollama status, tag stats
```

#### 4.1.2 Capture Flow (What Happens on `cortex add`)

1. **Instant save**: Note text is written to SQLite immediately. User gets confirmation in < 100ms. This is the critical path — it must be instant.
2. **Async enrichment** (background, non-blocking):
   - Compute embedding via sentence-transformers -> store in sqlite-vec
   - Send note text to local Ollama model with extraction prompt -> get back tags, category, summary, sentiment
   - Write enrichment data back to DB (update note, insert tags)
3. **CLI output**: `✓ Note saved (id: a1b2c3d4) — enrichment processing...`
   - If `--wait` flag is passed: blocks until enrichment completes and shows extracted metadata

#### 4.1.3 CLI Output Style
Clean, minimal. No emoji overload. Think professional terminal output:
```
$ cortex add "Need to prep deck for SF trip. Focus on unit economics slide."
✓ Saved  a1b2c3d4  (12 words)

$ cortex add "Need to prep deck for SF trip" --wait
✓ Saved  a1b2c3d4  (12 words)
  Tags:     fundraising, pitch-deck, sf-trip
  Category: business
  Summary:  Prep investor deck focused on unit economics for SF trip
```

---

### 4.2 Web UI — Browse, Search & Converse

The retrieval and exploration interface. Server-rendered with HTMX for interactivity.

#### 4.2.1 Design Direction
Clean, fast, editorial. Dark mode default. Think: a premium terminal meets a reading app. The aesthetic of someone who values function but has taste.

**Color Palette:**
- Background: `#111111` (primary), `#1a1a1a` (cards/surfaces), `#222222` (elevated)
- Text: `#e8e4df` (primary), `#9a958f` (secondary), `#5c5855` (muted)
- Accent (primary): `#c9a84c` (warm gold — for actions, highlights, active states)
- Accent (tags): `#4a7c6a` (muted sage — for tag pills)
- Accent (danger/delete): `#b85450` (muted red)
- Borders: `#2a2a2a`
- Code/mono background: `#161616`

**Typography:**
- Headings: Inter (700) or system-ui — clean, no-fuss
- Body / Notes: Inter (400/500) — optimized for reading
- Mono (tags, IDs, timestamps): JetBrains Mono (400)
- Note text display: slightly larger (17-18px), comfortable reading line-height (1.65)

**Layout:**
- Max content width: 720px (reading-optimized, like a good blog)
- Sidebar: minimal — just nav links, collapsible
- Cards: subtle borders, no heavy shadows, generous padding
- Spacing: airy, not cramped

#### 4.2.2 Pages

**1. Feed (Home) — `/`**
Reverse-chronological stream of notes. The default view.
- Each note card shows: timestamp (relative, e.g., "2 hours ago"), raw text (truncated at 3 lines for long notes, expandable), tags as small pills, category badge, source icon (CLI/web)
- Date separators between day groups ("Today", "Yesterday", "Feb 15")
- HTMX infinite scroll — loads more notes as you scroll
- Quick-filter bar at top: filter by category, tag, date range
- "New Note" floating action — opens inline compose form at top of feed

**2. Note Detail — `/notes/{id}`**
Full note view with all metadata.
- Raw text (full, with markdown rendering if applicable)
- Metadata sidebar or below-note section: tags, category, sentiment, summary, source, created date, word count
- Edit button -> inline edit with save
- Delete (with confirmation)
- "Related notes" section — 5 most semantically similar notes (via embedding similarity)
- "Ask about this" -> opens agent panel scoped to this note

**3. Search — `/search`**
The power interface. Three search modes:
- **Keyword** (FTS5): Traditional text search, fast, exact matching
- **Semantic** (embeddings): "Notes about investor concerns" finds notes even if they don't contain those exact words
- **Agent** (conversational): "What have I been thinking about pricing this month?" — uses the local model or Claude to synthesize across multiple notes

UI:
- Single search bar at top, big and prominent
- Mode toggle: Keyword | Semantic | Agent (default: Semantic)
- Results show: note snippet with highlighted matches, relevance score, date, tags
- Agent mode: chat-like interface below the search bar. Shows the agent's answer with citations (links to specific notes it referenced)
- Search is HTMX-powered — results appear without page reload

**4. Tags — `/tags`**
Tag explorer for browsing by topic.
- Tag cloud or grouped list, sorted by usage count
- Click a tag -> filtered note feed for that tag
- Tag groups: Topic, Entity, Project, Person, Location
- Tag merge tool (combine duplicates — "fundraising" + "fundraise" -> "fundraising")

**5. Compose — `/compose`**
Web-based note capture for when you're already in the browser.
- Large textarea, auto-expanding, markdown support
- Optional: toggle "Journal mode" for longer entries
- Save button + keyboard shortcut (Cmd+Enter)
- After save: shows extracted metadata (tags, category, summary) with option to edit
- No mandatory fields. Just text and a save button.

**6. Stats — `/stats`**
Light analytics dashboard. Not critical for Phase 1 but useful.
- Notes per day/week/month (bar chart)
- Top tags (last 30 days)
- Category distribution (pie/donut)
- Capture source breakdown (CLI vs. web)
- Total notes, total words, DB size

---

### 4.3 AI Layer — Auto-Enrichment

#### 4.3.1 Tagging Pipeline (Runs on Every Note Save)

When a note is saved, the enrichment pipeline runs asynchronously:

**Step 1: Embedding Generation**
```python
# sentence-transformers — runs in-process, no API call
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(note_text)
# Store in sqlite-vec
```
- Loaded once at server startup, stays in memory
- Encoding a single note: ~10-50ms on CPU
- This is the fastest step

**Step 2: Metadata Extraction (Ollama)**
```
System: You are a metadata extraction engine for a personal notes system owned by
Patrick, CEO of Annora AI (a manufacturing software company). Extract structured
metadata from the note below.

Rules:
- Tags: 2-6 lowercase, hyphenated tags. Draw from both business topics (manufacturing,
  fundraising, sales, product, engineering, customers, partnerships, hiring, strategy,
  marketing, operations) and personal topics (health, fitness, relationships, journaling,
  personal-development, travel, ideas, reading). Include entity names when mentioned
  (people, companies, places) as their own tags.
- Category: exactly one of: business, personal, idea, journal, meeting, task, reference
- Summary: one sentence, max 20 words, capturing the core point
- Sentiment: one of: positive, negative, neutral, mixed
- Is Journal: true if this is a longer personal reflection or journal entry, false otherwise

Respond ONLY with valid JSON, no explanation:
{
  "tags": [{"name": "tag-name", "group": "topic|entity|project|person|location"}],
  "category": "...",
  "summary": "...",
  "sentiment": "...",
  "is_journal": false
}

Note:
"""
{note_text}
"""
```

- Model: Llama 3.2 3B via Ollama (fast, good at structured extraction)
- Expected latency: 1-3 seconds per note
- Runs async — user doesn't wait for this
- If Ollama is unavailable, note still saves. Enrichment retries later.

**Step 3: Tag Normalization**
- Lowercase all tags
- Deduplicate against existing tags table (fuzzy match: "fundraise" -> existing "fundraising")
- Increment usage_count for existing tags
- Insert new tags with tag_group

#### 4.3.2 Retry Queue
If enrichment fails (Ollama down, model loading, etc.):
- Note is flagged as `unenriched` (summary IS NULL)
- Background task retries unenriched notes every 60 seconds
- CLI: `cortex enrich --retry` forces re-enrichment of all unenriched notes
- `cortex enrich --all` re-runs enrichment on everything (useful after model upgrade)

---

### 4.4 AI Layer — Search & Retrieval Agent

#### 4.4.1 Search Modes

**Keyword Search (FTS5)**
- Direct SQLite FTS5 query
- Supports boolean operators: `pricing AND investor`
- Fastest mode, exact matching
- Used as a component within the agent flow too

**Semantic Search (Embeddings)**
- Embed the query using the same sentence-transformers model
- sqlite-vec cosine similarity search against all note embeddings
- Return top-K results with similarity scores
- Optionally filtered by category, tag, date range
- Primary search mode for the web UI

**Agent Search (Conversational Q&A)**
- The most powerful mode. Uses an LLM to understand the question, search, and synthesize.
- Flow:
  1. User asks a natural language question
  2. System runs semantic search + keyword search to find relevant notes
  3. Top results (raw text + metadata) are injected as context into the LLM prompt
  4. LLM synthesizes an answer with citations to specific notes
  5. If using local model: Ollama handles this (good for simple retrieval questions)
  6. If using Claude: deeper synthesis, pattern recognition, multi-note analysis

#### 4.4.2 Agent System Prompt

```
You are Cortex, a personal knowledge retrieval agent for Patrick, CEO of Annora AI.
You have access to Patrick's personal notes — a mix of business thoughts, meeting notes,
ideas, journal entries, and random brain dumps.

Your job:
1. Answer questions by finding and synthesizing relevant notes
2. Always cite which notes you're drawing from (use note IDs)
3. If you can't find relevant notes, say so — don't hallucinate
4. Be direct and concise. Patrick values speed.
5. If the question is ambiguous, make your best interpretation and note your assumption

You will receive relevant notes as context. Each note includes:
- ID, date, tags, category, and the full text

Respond naturally. If quoting a note, reference it as [note:ID].
```

#### 4.4.3 Model Selection Logic
```python
def select_model(query: str, note_count: int) -> str:
    """
    Pick the right model for the query.
    - Simple retrieval ("what did I say about X?") -> local model
    - Synthesis ("what patterns do I see in my fundraising notes?") -> Claude
    - User can force Claude with a flag or toggle in UI
    """
    if user_preference == "always_local":
        return "ollama"
    if user_preference == "always_claude":
        return "claude"

    # Default: local for retrieval, Claude for synthesis
    # Heuristic: synthesis queries tend to be more abstract,
    # retrieval queries reference specific things
    synthesis_signals = ["pattern", "trend", "summary", "analyze",
                         "compare", "theme", "insight", "overall"]
    if any(signal in query.lower() for signal in synthesis_signals):
        return "claude"
    return "ollama"
```

---

## 5. UI/UX SPECIFICATIONS

### 5.1 Design System

**Components (HTMX + Jinja + Tailwind):**
- **Note Card**: rounded-lg, subtle border, `bg-[#1a1a1a]`, padding-5, hover state with slightly lighter bg. Timestamp in mono, tags as small rounded pills in sage green.
- **Tag Pill**: `bg-[#4a7c6a]/20 text-[#4a7c6a]`, rounded-full, px-2 py-0.5, text-xs, font-mono
- **Category Badge**: similar to tag but with distinct color per category (gold for business, sage for personal, blue-gray for idea, etc.)
- **Search Bar**: large, full-width, `bg-[#161616]`, rounded-xl, padding-4, text-lg, gold border on focus
- **Buttons**: minimal, ghost-style by default. Primary action: gold bg with dark text. Destructive: muted red.
- **Agent Chat**: message bubbles — user messages right-aligned dark, agent responses left-aligned with subtle border. Note citations as clickable inline links.

### 5.2 Key Interactions (HTMX)
- **Note feed infinite scroll**: `hx-get="/partials/notes?page=2" hx-trigger="revealed" hx-swap="afterend"`
- **Search results**: `hx-post="/search" hx-trigger="keyup changed delay:300ms" hx-target="#results"` — live results as you type
- **Quick filter**: clicking a tag/category pill filters the feed via HTMX without page reload
- **Note save**: `hx-post="/notes" hx-swap="afterbegin" hx-target="#feed"` — new note appears at top of feed instantly
- **Agent chat**: `hx-post="/agent/ask"` with streaming response via SSE (Server-Sent Events) for typewriter effect
- **Note expand/collapse**: `hx-get="/partials/note/{id}/full"` to expand truncated notes inline

### 5.3 Responsive Behavior
- Mobile (< 768px): single column, no sidebar, sticky search bar at top, bottom nav
- Desktop (>= 768px): optional slim sidebar, centered content column (max 720px), search bar prominent
- The web UI is Phase 1 desktop-optimized but should not break on mobile

---

## 6. API ROUTES

### 6.1 Route Structure

```
app/
├── api/
│   ├── notes/
│   │   ├── POST    /api/notes              # Create note
│   │   ├── GET     /api/notes              # List notes (paginated, filterable)
│   │   ├── GET     /api/notes/{id}         # Get single note with metadata
│   │   ├── PATCH   /api/notes/{id}         # Update note text
│   │   ├── DELETE  /api/notes/{id}         # Delete note
│   │   └── GET     /api/notes/{id}/related # Get semantically similar notes
│   │
│   ├── search/
│   │   ├── POST    /api/search/keyword     # FTS5 keyword search
│   │   ├── POST    /api/search/semantic    # Embedding similarity search
│   │   └── POST    /api/search/agent       # AI agent Q&A (SSE streaming)
│   │
│   ├── tags/
│   │   ├── GET     /api/tags               # List all tags (with counts)
│   │   ├── PATCH   /api/tags/{id}          # Rename/merge tag
│   │   └── DELETE  /api/tags/{id}          # Delete tag (removes from notes)
│   │
│   ├── collections/
│   │   ├── POST    /api/collections        # Create collection
│   │   ├── GET     /api/collections        # List collections
│   │   ├── POST    /api/collections/{id}/notes  # Add note to collection
│   │   └── DELETE  /api/collections/{id}/notes/{note_id}  # Remove note
│   │
│   ├── enrichment/
│   │   ├── POST    /api/enrichment/retry   # Re-enrich failed notes
│   │   └── POST    /api/enrichment/all     # Re-enrich all notes
│   │
│   └── stats/
│       └── GET     /api/stats              # Dashboard stats
│
├── pages/                                   # Jinja-rendered HTML
│   ├── GET     /                           # Feed (home)
│   ├── GET     /notes/{id}                 # Note detail
│   ├── GET     /search                     # Search page
│   ├── GET     /tags                       # Tag explorer
│   ├── GET     /compose                    # Web compose
│   └── GET     /stats                      # Stats dashboard
│
└── partials/                               # HTMX partial templates
    ├── GET     /partials/notes             # Note list fragment (for infinite scroll)
    ├── GET     /partials/note/{id}/full    # Full note text (for expand)
    ├── GET     /partials/search-results    # Search results fragment
    └── GET     /partials/agent-response    # Agent streaming response
```

### 6.2 Agent API Detail

```python
# POST /api/search/agent
# Request:
{
    "query": "What have I been thinking about pricing?",
    "model": "auto",           # "auto", "local", "claude"
    "date_filter": {           # optional
        "after": "2025-01-01",
        "before": "2025-02-18"
    },
    "category_filter": null,   # optional: "business", "personal", etc.
    "tag_filter": null          # optional: ["pricing", "strategy"]
}

# Response: SSE stream
# event: token
# data: {"text": "Based on your notes, ..."}
#
# event: citations
# data: {"note_ids": ["a1b2c3d4", "e5f6g7h8"]}
#
# event: done
# data: {"model_used": "claude", "notes_searched": 342, "notes_cited": 3}
```

---

## 7. FILE STRUCTURE

```
cortex/
├── KERNEL.md                      # This file
├── pyproject.toml                 # Project config (uv/pip, dependencies, metadata)
├── justfile                       # Task runner commands
├── .env                           # ANTHROPIC_API_KEY (optional), OLLAMA_MODEL, DB_PATH
├── .env.example
├── Dockerfile                     # Optional containerized deployment
│
├── src/
│   ├── cortex/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app factory + lifespan (model loading)
│   │   ├── config.py              # Settings from env vars (pydantic-settings)
│   │   │
│   │   ├── cli/
│   │   │   ├── __init__.py
│   │   │   ├── app.py             # Typer app with all commands
│   │   │   ├── commands/
│   │   │   │   ├── add.py         # cortex add
│   │   │   │   ├── search.py      # cortex search
│   │   │   │   ├── recent.py      # cortex recent
│   │   │   │   ├── journal.py     # cortex journal
│   │   │   │   ├── serve.py       # cortex serve
│   │   │   │   ├── enrich.py      # cortex enrich
│   │   │   │   └── status.py      # cortex status
│   │   │   └── formatting.py      # Rich console output helpers
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── notes.py       # /api/notes endpoints
│   │   │   │   ├── search.py      # /api/search endpoints
│   │   │   │   ├── tags.py        # /api/tags endpoints
│   │   │   │   ├── collections.py # /api/collections endpoints
│   │   │   │   ├── enrichment.py  # /api/enrichment endpoints
│   │   │   │   └── stats.py       # /api/stats endpoints
│   │   │   └── pages.py           # Jinja page routes (/, /search, /tags, etc.)
│   │   │
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py      # SQLite connection manager (with sqlite-vec loaded)
│   │   │   ├── migrations.py      # Schema creation + migration runner
│   │   │   ├── queries/
│   │   │   │   ├── notes.py       # Note CRUD queries
│   │   │   │   ├── tags.py        # Tag queries
│   │   │   │   ├── search.py      # FTS5 + vector search queries
│   │   │   │   └── stats.py       # Aggregation queries
│   │   │   └── schema.sql         # Full DDL (tables, indexes, FTS, triggers)
│   │   │
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── embeddings.py      # sentence-transformers model loading + encoding
│   │   │   ├── enrichment.py      # Ollama tagging pipeline
│   │   │   ├── agent.py           # Search agent (query -> search -> synthesize)
│   │   │   ├── prompts.py         # All LLM prompts (extraction, agent, etc.)
│   │   │   └── ollama_client.py   # Ollama HTTP client wrapper
│   │   │
│   │   ├── templates/
│   │   │   ├── base.html          # Base layout (head, nav, scripts)
│   │   │   ├── feed.html          # Home / note feed
│   │   │   ├── note_detail.html   # Single note view
│   │   │   ├── search.html        # Search page
│   │   │   ├── tags.html          # Tag explorer
│   │   │   ├── compose.html       # Web compose form
│   │   │   ├── stats.html         # Stats dashboard
│   │   │   └── partials/
│   │   │       ├── note_card.html       # Single note card fragment
│   │   │       ├── note_list.html       # Note list fragment (infinite scroll)
│   │   │       ├── search_results.html  # Search results fragment
│   │   │       ├── agent_message.html   # Agent response message
│   │   │       └── tag_cloud.html       # Tag cloud fragment
│   │   │
│   │   └── static/
│   │       ├── css/
│   │       │   └── app.css        # Tailwind output (built via standalone CLI)
│   │       └── js/
│   │           └── htmx.min.js    # HTMX (vendored, no CDN dependency)
│   │
│   └── tests/
│       ├── test_enrichment.py     # Tagging pipeline tests
│       ├── test_search.py         # Search accuracy tests
│       ├── test_db.py             # Database query tests
│       └── conftest.py            # Fixtures (test DB, sample notes)
│
├── data/
│   └── cortex.db                  # SQLite database (gitignored, auto-created)
│
└── docs/
    ├── kernel.md                  # This file (symlinked or copied)
    ├── architecture.md            # Generated during build
    └── progress.md                # Implementation log
```

---

## 8. IMPLEMENTATION PLAN (Phased)

### Phase 1: Foundation — Capture & Store (Steps 1-4)

**Step 1: Project Scaffold**
- Initialize Python project with uv
- Set up pyproject.toml with dependencies
- Create justfile with common commands
- Set up directory structure from Section 7
- Configure Ruff for linting/formatting
- Create .env.example

**Step 2: Database Setup**
- SQLite connection manager with sqlite-vec extension loaded
- Schema creation from Section 3
- Migration runner
- `cortex init` command to create DB and run schema

**Step 3: CLI Capture (No AI Yet)**
- `cortex add "text"` saves note to DB
- `cortex add --long` opens $EDITOR
- `cortex journal` opens $EDITOR with journal flag
- `cortex recent` lists last 10 notes
- `cortex recent --today` filters to today

**Step 4: Web UI Shell**
- FastAPI app with Jinja2 templates
- Base layout: dark theme, Tailwind, HTMX loaded
- Feed page (/) renders notes
- Note detail page (/notes/{id})
- Compose page (/compose)
- HTMX infinite scroll on feed
- `cortex serve` starts the web server

### Phase 2: Intelligence — Auto-Enrichment (Steps 5-7)

**Step 5: Embedding Pipeline**
- Load sentence-transformers model at startup
- On note save: generate embedding, store in sqlite-vec
- Backfill command: `cortex enrich --embeddings`

**Step 6: Ollama Tagging Pipeline**
- Ollama HTTP client
- Extraction prompt from Section 4.3.1
- Async enrichment after note save
- Tag normalization + deduplication
- Retry queue for failed enrichments

**Step 7: Web UI Enrichment Display**
- Note cards show tags, category badge, summary
- Tag explorer page (/tags)
- Category filter bar on feed
- Note detail shows all metadata

### Phase 3: Retrieval — Search & Agent (Steps 8-10)

**Step 8: Keyword + Semantic Search**
- FTS5 keyword search endpoint
- Semantic search endpoint
- Search page with mode toggle
- HTMX live search results

**Step 9: Related Notes**
- Note detail: "Related Notes" section
- sqlite-vec KNN query excluding current note

**Step 10: Agent Search**
- Agent endpoint with SSE streaming
- Local mode (Ollama) and Claude mode
- Auto model selection
- Chat-like interface on search page
- Note citations in responses

### Phase 4: Polish & Extend (Steps 11-14)

**Step 11: Collections**
- Create/manage collections via web UI
- Add/remove notes from collections
- Collection view page

**Step 12: Stats Dashboard**
- Notes per day/week chart
- Top tags, category distribution
- Capture source breakdown

**Step 13: CLI Search**
- `cortex search "query"` — semantic search in terminal
- `cortex search "query" --agent` — agent search
- `cortex search "query" --keyword` — FTS5 search

**Step 14: Hardening**
- Error handling on all routes
- Input validation (Pydantic models)
- DB backup command
- Export command
- Performance check

### Phase 5: Future — Mobile & Integrations (Steps 15+)

**Step 15: WhatsApp Integration**
**Step 16: Mobile Web PWA**
**Step 17: Voice Notes**

---

## 9. CRITICAL RULES FOR CLAUDE CODE

See CLAUDE.md in project root.

---

## 10. DEPENDENCIES

### 10.1 Python Packages (pyproject.toml)

```toml
[project]
name = "cortex"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",
    "pydantic-settings>=2.5.0",
    "typer[all]>=0.12.0",
    "aiosqlite>=0.20.0",
    "sqlite-vec>=0.1.0",
    "sentence-transformers>=3.0",
    "httpx>=0.27.0",
    "anthropic>=0.39.0",
    "sse-starlette>=2.0.0",
    "python-dateutil>=2.9.0",
]
```

### 10.2 External Requirements
- **Ollama**: Must be installed separately. `brew install ollama` (macOS) or from https://ollama.ai
- **Ollama model**: Pull before first use: `ollama pull llama3.2:3b`
- **Tailwind CSS**: Standalone CLI binary, no Node
- **sqlite-vec**: Installed via pip, includes compiled extension

---

## 11. MEMORY BANK FILES

When implementing, maintain these files in the `docs/` directory:

- **kernel.md** (this file) — the full spec, reference for all decisions
- **architecture.md** — generated after Phase 1, documents actual implementation as built
- **progress.md** — updated after each step with: what was done, what was deferred, decisions made, issues encountered

---

*"Your brain is for having ideas, not holding them." — David Allen*

*This kernel makes that literal. Capture everything, let the AI organize it, ask for it back when you need it. Now build it.*

Last thing. Make something beautiful.
