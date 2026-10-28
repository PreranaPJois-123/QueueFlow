#!/bin/sh
# Container start: migrate, bootstrap the first admin (if configured), optionally
# seed sample venues, refresh the Wayzen knowledge index, then serve.
set -e
alembic upgrade head
QUEUEFLOW_BOOTSTRAP_ADMIN=1 python -m app.provision_user
if [ "${SEED_SAMPLE_DATA:-false}" = "true" ]; then
  python -m app.seed
fi
# Re-embeds only changed documents. A failing remote embedding provider must not
# keep the API down, so this step is allowed to fail with a warning.
python -m app.rag.ingest || echo "WARNING: knowledge ingestion failed; Wayzen retrieval may be stale"
# --proxy-headers: trust X-Forwarded-For from the nginx edge (the backend port is
# not published publicly), so rate limits see real client addresses.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
