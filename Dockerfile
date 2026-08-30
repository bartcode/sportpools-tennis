# ── Stage 1: build the React frontend ──────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── Stage 2: Python runtime with the API and the built bundle ─────────
FROM python:3.13-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --compile-bytecode

COPY --from=frontend /build/dist ./web-dist

ENV SPORTPOOLS_WEB_DIR=/app/web-dist \
    SPORTPOOLS_UI_HOST=0.0.0.0 \
    SPORTPOOLS_UI_PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --system --uid 1000 app \
    && mkdir -p /app/data /app/.cache \
    && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"

CMD ["sportpools-ui"]
