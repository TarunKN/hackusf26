# ── FormCoach API — optimized for low memory (256MB target) ───────────────────
FROM python:3.11-slim

WORKDIR /app

# Install only what's needed — no build-essential (saves ~200MB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# --no-cache-dir keeps image small
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/          ./api/
COPY fitness-agents/ ./fitness-agents/
COPY shared/       ./shared/
COPY frontend/     ./frontend/

# Create upload directory
RUN mkdir -p /tmp/formcoach_uploads

# ── PYTHONPATH: make shared/ and fitness-agents/ importable from anywhere ─────
# This replaces all the sys.path.append() calls in the agent files.
# /app          → finds `shared`, `api`
# /app/fitness-agents → finds `agents` package
ENV PYTHONPATH="/app:/app/fitness-agents"

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=2 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with 1 worker (fits in 256MB), no reload in production.
# Use shell form so $PORT is expanded — Railway injects PORT at runtime.
CMD python -m uvicorn api.main:api \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 1 \
    --timeout-keep-alive 30 \
    --log-level info
