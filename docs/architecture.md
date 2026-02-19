# Cortex — Architecture Document

> Generated after implementation. Documents the actual system as built.

---

## System Overview

Cortex is a local-first personal knowledge capture and retrieval system. Two interfaces (CLI + Web) hit the same FastAPI backend. The backend talks to SQLite for storage, Ollama for local AI (tagging + basic search), and optionally Claude for deep Q&A.

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

## Module Layout

### `src/cortex/`

| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI app factory, lifespan (model loading, background enrichment loop), middleware |
| `config.py` | Pydantic-settings config from `.env` — DB path, Ollama URL, Anthropic key, etc. |

### `src/cortex/cli/`

| Module | Purpose |
|--------|---------|
| `app.py` | Typer app with all CLI commands registered |
| `commands/add.py` | `cortex add` — instant note save + background enrichment |
| `commands/search.py` | `cortex search` — semantic/keyword/agent search in terminal |
| `commands/recent.py` | `cortex recent` — list recent notes |
| `commands/journal.py` | `cortex journal` — open $EDITOR for journal entry |
| `commands/serve.py` | `cortex serve` — start the web server |
| `commands/enrich.py` | `cortex enrich` — retry/re-run enrichment pipeline |
| `commands/status.py` | `cortex status` — system health check |
| `formatting.py` | Rich console output helpers |

### `src/cortex/api/`

| Module | Purpose |
|--------|---------|
| `pages.py` | Jinja2 page routes (/, /notes/{id}, /search, /tags, /compose, /collections, /stats) + HTMX partials |
| `routes/notes.py` | REST CRUD for notes + enrichment status endpoint + related notes |
| `routes/search.py` | Keyword, semantic, and agent search endpoints (SSE streaming for agent) |
| `routes/tags.py` | Tag list, rename, merge, delete |
| `routes/collections.py` | Collection CRUD + note membership |
| `routes/enrichment.py` | Trigger enrichment retry/re-run |
| `routes/stats.py` | Dashboard statistics endpoint |

### `src/cortex/db/`

| Module | Purpose |
|--------|---------|
| `connection.py` | Sync + async SQLite connection factories (loads sqlite-vec extension) |
| `migrations.py` | Schema creation from `schema.sql`, version tracking |
| `schema.sql` | Full DDL — tables, indexes, FTS5, triggers |
| `queries/notes.py` | Note CRUD, enrichment update, unenriched note finder |
| `queries/tags.py` | Tag CRUD, merge, rename |
| `queries/search.py` | FTS5 keyword search, sqlite-vec semantic search, related notes |
| `queries/stats.py` | Aggregation queries for dashboard |

### `src/cortex/ai/`

| Module | Purpose |
|--------|---------|
| `embeddings.py` | sentence-transformers model loading, encoding, blob conversion, sqlite-vec storage |
| `enrichment.py` | Full enrichment pipeline: embed + Ollama metadata extraction |
| `agent.py` | Search agent: query → retrieval (FTS5 + semantic) → LLM synthesis (Ollama or Claude) |
| `ollama_client.py` | Async HTTP client for Ollama API (generate + stream) |
| `prompts.py` | All LLM prompts (extraction, agent system prompt, synthesis signals) |

## Data Model

### Core Tables
- **notes** — text + metadata (summary, category, sentiment, source, word_count)
- **tags** — unique tags with tag_group (topic, entity, project, person, location)
- **note_tags** — many-to-many with confidence scores
- **note_embeddings** — sqlite-vec virtual table (384-dim float vectors)
- **notes_fts** — FTS5 virtual table with sync triggers
- **search_history** — query log with type and model used
- **collections** / **note_collections** — optional manual grouping

### Key Patterns
- **Hex ID generation**: `lower(hex(randomblob(16)))` — 32-char random hex
- **FTS5 sync**: INSERT/UPDATE/DELETE triggers keep `notes_fts` in sync with `notes`
- **Tag upsert**: `INSERT ON CONFLICT DO UPDATE SET usage_count = usage_count + 1`
- **Cascade deletes**: `ON DELETE CASCADE` on all foreign keys

## Request Flow

### Note Save (< 100ms critical path)
1. CLI/Web submits text → `INSERT INTO notes` → return ID immediately
2. Background: `asyncio.create_task` fires enrichment
3. Enrichment: embed text → store in sqlite-vec → Ollama extraction → update note + tags
4. If Ollama is down: note is saved, enrichment retries every 60s via background loop

### Agent Search (SSE streaming)
1. User submits query
2. Embed query via sentence-transformers
3. Run semantic search (top 10) + keyword search (top 5) in parallel
4. Deduplicate and merge results (cap at 15 notes)
5. Select model: local for retrieval, Claude for synthesis (auto heuristic)
6. Stream LLM response as SSE events: `token` → `citations` → `done`

### Scoped Agent (Ask About This Note)
1. User clicks "Ask about this" on note detail
2. System uses the note + its 5 most related notes as context
3. Same LLM pipeline as global agent, but context is pre-scoped

## Background Tasks

- **Enrichment retry loop**: Runs every 60 seconds in `asyncio.create_task` during lifespan
  - Queries for unenriched notes (`summary IS NULL`)
  - Processes up to 10 notes per cycle
  - Graceful failure per note — never crashes the loop

## Design System

- Background: `#111111` (primary), `#1a1a1a` (cards), `#222222` (elevated)
- Text: `#e8e4df` (primary), `#9a958f` (secondary), `#5c5855` (muted)
- Accents: `#c9a84c` (gold), `#4a7c6a` (sage), `#b85450` (danger)
- Fonts: Inter (body), JetBrains Mono (code/tags/timestamps)
- Content max-width: 720px
- Sidebar: 240px fixed, collapses on mobile (< 768px)
- Mobile: bottom nav bar replaces sidebar

## Dependencies

### Runtime
- fastapi, uvicorn, jinja2, python-multipart, pydantic-settings
- aiosqlite, sqlite-vec (vector search in SQLite)
- sentence-transformers (embedding model)
- httpx (Ollama HTTP client)
- anthropic (Claude API, optional)
- sse-starlette (SSE streaming)
- typer, rich (CLI)

### Dev
- ruff (lint/format), pyright (type checking)
- pytest, pytest-asyncio (testing)
