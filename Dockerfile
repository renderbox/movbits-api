# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV VENV=/opt/venv
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

COPY pyproject.toml ./
RUN mkdir -p src && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV VENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# libpq is needed at runtime by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY src/ ./src/
COPY manage.py ./
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

RUN DJANGO_SETTINGS_MODULE=movbitsapi.settings.prod \
    DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py collectstatic --noinput

EXPOSE 8080

CMD ["./entrypoint.sh"]
