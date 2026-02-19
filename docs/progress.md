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

### Step 11: Collections
- Collections API (create, list, add/remove notes, delete)
- Collections web UI: list page, detail page, sidebar nav link
- Full CRUD via web interface

### Step 12: Stats Dashboard
- Notes per day bar chart (30 days)
- Notes per week bar chart (12 weeks) with day/week toggle
- SVG donut chart for category distribution with color-coded legend
- Capture source breakdown (CLI vs web)
- Total notes, words, tags, DB size
- Enrichment status with retry button

### Step 13: CLI Search
- `cortex search "query"` — semantic search in terminal
- `cortex search "query" --agent` — agent search
- `cortex search "query" --keyword` — FTS5 search

### Step 14: Hardening
- Error handling on all routes
- Input validation via Pydantic models
- DB backup command
- Export command (JSON/CSV)
- Graceful degradation when Ollama is unavailable
- Comprehensive test suite (28 tests)

## Phase 4.5: Gap Fixes (Complete)

### Background Enrichment Retry
- asyncio background task retries unenriched notes every 60 seconds
- Runs in app lifespan, cleans up on shutdown
- Processes up to 10 notes per cycle with per-note error isolation

### Compose Metadata Display
- After saving a note, polls `/api/notes/{id}/enrichment` every 2 seconds
- Displays summary, category badge, sentiment, and tag pills when ready
- 30-second timeout with graceful fallback message

### "Ask About This" Feature
- Agent panel on note detail page with scoped search
- Sends `note_id` to agent API, which uses the note + related notes as context
- Same SSE streaming UX as global agent search

### Feed Date Range Filter
- Date picker inputs (from/to) in the feed filter bar
- Integrates with existing category and tag filters
- Filter params passed through to infinite scroll pagination

### Tag Merge UI
- Merge tool panel on tags page with source/target dropdowns
- Calls existing `PATCH /api/tags/{id}` merge endpoint
- Page reloads after successful merge

### Stats Charts Upgrade
- SVG donut chart for category distribution (no external libraries)
- Color-coded legend matching category badge colors
- Day/Week toggle for notes-over-time chart
- Week chart uses 12-week lookback with sage accent color

### Search Result Highlighting
- Query terms highlighted in search results with gold background
- Client-side highlighting via regex match on result text
- Filters out short words (< 3 chars) to avoid noise

### Infrastructure Fixes
- Fixed max content width to 720px (removed sidebar math from main-content)
- Infinite scroll pagination now shows "You've reached the beginning" at end
- `has_more` flag prevents empty scroll triggers
- Date filter params propagated through scroll pagination
- Dockerfile + .dockerignore for optional containerized deployment
- KERNEL.md added to repo and symlinked to docs/

## Decisions Made
- Used hatchling as build backend (modern, fast)
- Inline CSS in base.html rather than separate Tailwind build step (simpler, no Node dependency)
- HTMX stub for offline development (replace with real htmx.min.js in production)
- All templates use Jinja2 inheritance pattern
- SSE via sse-starlette for agent streaming
- SVG-based donut chart instead of Chart.js (zero external JS dependencies)
- Background enrichment via asyncio task instead of APScheduler (simpler, no extra dependency)
- Enrichment polling in compose uses 2-second intervals (balance between responsiveness and overhead)

## Known Limitations
- HTMX stub needs to be replaced with production htmx.min.js
- Tailwind standalone CLI needed for full CSS rebuild
- sentence-transformers model download required on first run
- Ollama must be installed separately
- Date range filter uses native browser date pickers (styling varies by browser)
