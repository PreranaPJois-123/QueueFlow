FROM python:3.12-slim AS base

WORKDIR /app

# System deps needed to build psycopg2 and bcrypt wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt

COPY . .

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
        CMD curl -fsS http://127.0.0.1:${PORT:-8000}/api/health >/dev/null || exit 1

# Migrations, admin bootstrap, optional seed and knowledge ingestion are all
# idempotent, so they are safe on every start. See docker-entrypoint.sh.
CMD ["./docker-entrypoint.sh"]
