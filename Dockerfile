# Cortex — Local-first AI knowledge capture system
# Optional containerized deployment

FROM python:3.11-slim AS base

# System deps for sqlite-vec and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "." 2>/dev/null || \
    pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "jinja2>=3.1.0" \
    "python-multipart>=0.0.9" \
    "pydantic-settings>=2.5.0" \
    "typer[all]>=0.12.0" \
    "aiosqlite>=0.20.0" \
    "sqlite-vec>=0.1.0" \
    "sentence-transformers>=3.0" \
    "httpx>=0.27.0" \
    "anthropic>=0.39.0" \
    "sse-starlette>=2.0.0" \
    "python-dateutil>=2.9.0"

# Copy application code
COPY src/ src/
COPY justfile .
COPY .env.example .env.example

# Create data directory for SQLite
RUN mkdir -p data

# Pre-download the embedding model so startup is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Expose the web UI port
EXPOSE 8833

# Persistent volume for database
VOLUME ["/app/data"]

# Environment defaults
ENV DB_PATH=/app/data/cortex.db \
    OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    OLLAMA_MODEL=llama3.2:3b \
    HOST=0.0.0.0 \
    PORT=8833

# Initialize DB and start server
CMD ["sh", "-c", "python -m cortex.cli.app init && uvicorn cortex.main:app --host 0.0.0.0 --port 8833"]
