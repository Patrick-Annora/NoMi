# CLAUDE.md

## Project
Cortex — A local-first AI-powered personal knowledge capture and retrieval system.

## Tech Stack
- Python 3.12+, FastAPI, SQLite + sqlite-vec + FTS5
- Jinja2 + HTMX + Tailwind CSS (no JS frameworks)
- Typer for CLI
- Ollama (local LLM for tagging + basic Q&A)
- sentence-transformers for embeddings
- Anthropic Claude API (optional, for deep Q&A)

## Architecture Rules
- Local-first. Everything works without internet except Claude API calls.
- SQLite is the only data store. No Redis, no Postgres, no external DBs.
- Embedding model loads once at startup and stays in memory.
- Ollama calls are async and non-blocking. Note saves are NEVER blocked by AI processing.
- All API routes return JSON. All page routes return Jinja-rendered HTML.
- HTMX handles all dynamic UI updates. No React, no Vue, no Svelte.
- Tailwind via standalone CLI binary — no Node.js in this project at all.

## Code Style
- Type hints everywhere. Pyright strict mode must pass.
- Pydantic models for all API request/response schemas.
- Async functions for all FastAPI route handlers.
- Use `aiosqlite` for async database access in the web server.
- Synchronous SQLite access is fine in CLI commands.
- f-strings over .format() or %.
- Docstrings on all public functions (Google style).
- Ruff for formatting and linting. No exceptions.

## File Organization
- One module per concern. Don't put DB queries in route handlers.
- All SQL lives in db/queries/ modules as functions, not raw strings in routes.
- All LLM prompts live in ai/prompts.py — never inline in other modules.
- Templates use Jinja2 inheritance: base.html → page templates → partials.

## Common Commands
- `just dev` — start FastAPI dev server with reload
- `just cli` — run CLI commands (`just cli add "note text"`)
- `just lint` — ruff check + pyright
- `just fmt` — ruff format
- `just test` — pytest
- `just css` — rebuild Tailwind CSS
- `just init` — initialize database

## Critical Patterns
- Note save MUST complete in < 100ms. Enrichment is ALWAYS async/background.
- Embedding search uses cosine similarity via sqlite-vec. Do not implement custom distance functions.
- Tag normalization must handle plurals and minor variations. Use simple heuristics (stem matching), not an NLP library.
- FTS5 and semantic search should both be available. The agent combines them.
- SSE streaming for agent responses. Use FastAPI StreamingResponse with text/event-stream content type.
- All Ollama calls must have a timeout (30 seconds) and graceful fallback.

## Do NOT
- Do not use any JavaScript framework (React, Vue, Svelte, etc.)
- Do not use Node.js or npm for anything
- Do not add authentication (single-user local app)
- Do not use an ORM (no SQLAlchemy, no Tortoise)
- Do not store files in the database (notes are text only)
- Do not use WebSockets for streaming (use SSE — simpler, sufficient)
- Do not over-abstract. No repository pattern, no service layer. Keep it direct.
- Do not add Docker as a requirement. It's optional for portability only.
