# Cortex — task runner commands

# Start FastAPI dev server with reload
dev:
    uvicorn cortex.main:app --reload --host 127.0.0.1 --port 8833

# Run CLI commands
cli *ARGS:
    python -m cortex.cli.app {{ARGS}}

# Lint and type check
lint:
    ruff check src/
    pyright src/cortex/

# Format code
fmt:
    ruff format src/

# Run tests
test:
    pytest src/tests/ -v

# Initialize database
init:
    python -m cortex.cli.app init

# Rebuild Tailwind CSS
css:
    tailwindcss -i src/cortex/static/css/input.css -o src/cortex/static/css/app.css --minify

# Start server (production-like)
serve:
    uvicorn cortex.main:app --host 127.0.0.1 --port 8833

# Install dependencies
install:
    pip install -e ".[dev]"
