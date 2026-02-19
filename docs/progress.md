# Cortex — Implementation Progress

## Phase 1: Foundation (Complete)

### Step 1: Project Scaffold
- Initialized Python project with pyproject.toml (hatchling build backend)
- Set up directory structure per KERNEL.md Section 7
- Created justfile with common commands
- Created .env.example with all configuration options
- Configured Ruff for linting/formatting, Pyright for type checking

### Step 2: Database Setup
- SQLite connection manager with sqlite-vec extension loaded (db/connection.py)
- Full schema from KERNEL.md Section 3 (schema.sql)
- FTS5 virtual table with sync triggers
- sqlite-vec virtual table for 384-dimension embeddings
- Migration runner with version tracking
- Both sync (CLI) and async (web) connection patterns

### Step 3: CLI Capture
- `cortex add "text"` — saves note instantly, triggers background enrichment
- `cortex add --long` — opens $EDITOR for multi-line notes
- `cortex add --wait` — blocks until enrichment completes, shows metadata
- `cortex journal` — opens $EDITOR with journal mode flag
- `cortex recent` / `cortex recent --today` — show recent notes
- `cortex status` — system status with Ollama health check
- `cortex init` — database initialization
- `cortex backup` — timestamped DB backup
- `cortex export --format json|csv` — full data export
- Rich-formatted CLI output

### Step 4: Web UI Shell
- FastAPI app with Jinja2 templates and HTMX
- Dark theme design system with gold/sage accent colors
- Feed page (/) with date-grouped notes and infinite scroll
- Note detail page (/notes/{id}) with full metadata and related notes
- Compose page (/compose) with live word count, Cmd+Enter save
- Search page (/search) with keyword/semantic/agent mode toggle
- Tags page (/tags) with grouped tag cloud
- Stats page (/stats) with bar charts, category distribution, source breakdown
- HTMX partials for infinite scroll and live search
- Responsive layout with mobile bottom nav

## Phase 2: Intelligence (Complete)

### Step 5: Embedding Pipeline
- sentence-transformers all-MiniLM-L6-v2 model (384-dim)
- Model loaded once, cached in memory
- Embeddings stored in sqlite-vec virtual table
- `cortex enrich --embeddings` for backfill

### Step 6: Ollama Tagging Pipeline
- Async HTTP client for Ollama API
- Structured extraction prompt (tags, category, summary, sentiment)
- Tag normalization with upsert pattern
- Retry queue for failed enrichments
- `cortex enrich --retry` and `cortex enrich --all` commands

### Step 7: Web UI Enrichment Display
- Note cards show tags, category badges, source icons
- Tag explorer with grouped tag cloud
- Category filter bar on feed
- Note detail shows all metadata + AI summary

## Phase 3: Retrieval (Complete)

### Step 8: Keyword + Semantic Search
- FTS5 keyword search with boolean operators
- Semantic search via sqlite-vec cosine similarity
- Live search results via HTMX (debounced 300ms)
- Mode toggle UI (Keyword / Semantic / Agent)

### Step 9: Related Notes
- Note detail page shows 5 most similar notes
- sqlite-vec KNN query excluding current note
- Similarity scores displayed

### Step 10: Agent Search
- Agent endpoint with SSE streaming
- Local mode (Ollama) and Claude mode (Anthropic API)
- Auto model selection (retrieval vs synthesis heuristic)
- Note citations in responses
- Chat-like interface in web UI

## Phase 4: Polish (Complete)

### Step 11-14: Collections, Stats, CLI Search, Hardening
- Collections API (create, list, add/remove notes)
- Stats dashboard with charts
- CLI search with --keyword, --agent, --model flags
- Input validation via Pydantic models
- Graceful degradation when Ollama is unavailable
- Database backup and export commands
- Comprehensive test suite

## Decisions Made
- Used hatchling as build backend (modern, fast)
- Inline CSS in base.html rather than separate Tailwind build step (simpler, no Node dependency)
- HTMX stub for offline development (replace with real htmx.min.js in production)
- All templates use Jinja2 inheritance pattern
- SSE via sse-starlette for agent streaming

## Known Limitations
- HTMX stub needs to be replaced with production htmx.min.js
- Tailwind standalone CLI needed for full CSS rebuild
- sentence-transformers model download required on first run
- Ollama must be installed separately
