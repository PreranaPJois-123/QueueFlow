# Troubleshooting

**`docker compose up` says a variable is required.** Fill `JWT_SECRET_KEY`,
`POSTGRES_PASSWORD` and `APP_DB_PASSWORD` in `.env` (see README).

**Backend exits with "Production requires ..."** `ENV=production` validates config:
`JWT_SECRET_KEY` ≥ 32 chars, explicit `CORS_ORIGINS` without paths, a PostgreSQL URL.

**Sign-in works but every action says "Missing or invalid CSRF token".** The SPA and
API must share an origin (use the nginx proxy) and `CORS_ORIGINS` must equal the
exact browser origin (scheme, host, port). Clear cookies and sign in again.

**Signed in, then immediately signed out (HTTP).** `COOKIE_SECURE=true` cookies are
dropped over plain HTTP. Use HTTPS, or `COOKIE_SECURE=false` for local/demo only.

**Services/hospitals pages are empty.** No venues exist yet. Set
`SEED_SAMPLE_DATA=true` or run `docker compose exec backend python -m app.seed`, or
add venues under Administration → Venues. A doctor needs at least one service and
weekly hours before slots appear; Sundays have no hours in the sample data.

**No free times today.** Slots must be at least the venue's minimum notice ahead
(sample hospitals: 30 minutes) and inside working hours.

**Wayzen shows no sources / "couldn't find a help article".** `GET /api/health`
reports `knowledge_chunks`. `0` means the index is empty or was built with a different
embedding model: run `python -m app.rag.ingest`.

**Wayzen says limited mode.** No `LLM_PROVIDER`/`LLM_MODEL`/key configured. This is
expected; see README "Enabling Wayzen's AI answers".

**Re-index fails with a 502.** The remote embedding provider is unreachable or
rejected the key. Check `EMBEDDING_*` settings and container egress.

**Live updates say "Reconnecting".** The WebSocket could not connect: check that the
proxy forwards `Upgrade`/`Connection` headers (the bundled nginx does) and that the
page origin is in `CORS_ORIGINS`. Pages keep refreshing every 30 seconds meanwhile.

**Rate limited (429) during development.** Limits are per client IP. Behind a
different proxy than the bundled nginx, make sure it overwrites `X-Forwarded-For`.

**Existing database volume from QueueFlow 1.x.** The backend now connects as
`queueflow_app`, which the init script creates only for new volumes. For an existing
volume (after setting `APP_DB_PASSWORD` in `.env`):

```sh
docker compose up -d postgres
docker compose exec -T postgres sh /docker-entrypoint-initdb.d/01-app-role.sh
docker compose exec -T postgres psql -U queueflow -d queueflow < docker/postgres/upgrade-existing-volume.sql
docker compose up -d --build
```

The 1.x image (`postgres:16-alpine`) lacks pgvector; the new `pgvector/pgvector:pg16`
image reads the same data directory format (both PostgreSQL 16). Back up first.

**Backend tests refuse to start.** Set `TEST_DATABASE_URL` to a disposable PostgreSQL
database with the `vector` and `btree_gist` extensions available; every table in it
is truncated.
