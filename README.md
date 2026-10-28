# QueueFlow

Queue, appointment and reservation management for **hospitals, shops and hotels**,
with **Wayzen**, a retrieval-augmented assistant that answers from cited sources and
can prepare bookings that only execute after the user confirms.

- Customers browse hospitals (by specialization and doctor), shops (by service and
  staff member) and hotels; book real free slots or rooms; receive a booking
  reference and queue token; follow their live position on the day; get an in-app
  alert when their turn is about 20 minutes away; cancel or reschedule within policy.
- Staff run their assigned venues' queues (check in, start, complete, no-show,
  delays, pause) and the hotel front desk. Administrators manage venues, services,
  doctors/staff and schedules, room types, staff access and roles.
- The original walk-in queue features (join a service queue, staff call-next) are kept.

Venues created by the seed script are fictional and labelled **Sample** everywhere.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, React Router; Vitest + Testing Library |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, Argon2id |
| Data | PostgreSQL 16 with pgvector and btree_gist; Redis 7 (rate limits, locks, pub/sub) |
| Realtime | WebSockets, fanned out across instances through Redis pub/sub |
| AI | RAG over pgvector (configurable embeddings: offline lexical or OpenAI-compatible); LLM via OpenAI-compatible API (Groq, Llama 3.3 70B) or Anthropic | Ops | Docker Compose, nginx (non-root) reverse proxy, GitHub Actions |

Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Security: [docs/SECURITY.md](docs/SECURITY.md) ·
API: [docs/API.md](docs/API.md) (live OpenAPI at `/docs`) · Data model: [docs/schema.md](docs/schema.md) ·
AWS: [docs/AWS_EC2.md](docs/AWS_EC2.md) · Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) ·
What changed and what was verified: [docs/CHANGES.md](docs/CHANGES.md), [docs/VERIFICATION.md](docs/VERIFICATION.md)

## Run it with Docker Compose

```sh
cp .env.example .env
# Fill the three secrets:
sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -hex 32)/; \
        s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/; \
        s/^APP_DB_PASSWORD=.*/APP_DB_PASSWORD=$(openssl rand -hex 24)/" .env
# Optionally set INITIAL_ADMIN_EMAIL / _NAME / _PASSWORD in .env for a first admin.
docker compose up -d --build
curl http://localhost:8080/api/health
```

Open http://localhost:8080. On start the backend applies migrations, creates the
first admin (if configured), seeds sample venues (`SEED_SAMPLE_DATA=true`) and
indexes Wayzen's knowledge base. Only port 8080 is published publicly; PostgreSQL,
Redis and the backend listen on 127.0.0.1.

Useful commands:

```sh
docker compose exec backend python -m app.seed                          # sample venues (idempotent)
docker compose exec backend python -m app.seed --assign-staff EMAIL     # give a STAFF account the sample venues
docker compose exec backend python -m app.provision_user --email E --name 'N' --role STAFF
docker compose exec backend python -m app.rag.ingest                    # re-index knowledge
docker compose exec backend python -m app.rag.evaluate                  # retrieval metrics
./scripts/backup_db.sh                                                   # gzip pg_dump, keeps 7
```

> **Upgrading a database volume from QueueFlow 1.x?** The app now connects as a
> least-privilege role. See "Existing database volume" in
> [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Local development without Docker

Requires Python 3.12, Node 22, PostgreSQL 16 with the `vector` and `btree_gist`
extensions, and Redis.

```sh
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # set DATABASE_URL, JWT_SECRET_KEY
alembic upgrade head
python -m app.seed && python -m app.rag.ingest
uvicorn app.main:app --reload   # http://localhost:8000, docs at /docs

# Frontend (separate terminal)
cd frontend
cp .env.example .env            # VITE_API_URL=http://localhost:8000
npm ci && npm run dev           # http://localhost:5173
```

## Enabling Wayzen's AI answers

Without a model provider Wayzen runs in **limited mode**: it retrieves and cites the
matching help articles but writes no generated text. To enable generation set, for
example, `LLM_PROVIDER=anthropic`, `LLM_MODEL=<model id>`, `LLM_API_KEY=<key>`, or
`LLM_PROVIDER=openai_compatible` with `LLM_BASE_URL` (OpenAI, Ollama, vLLM...). For
semantic retrieval also set `EMBEDDING_PROVIDER=openai_compatible` and
`EMBEDDING_MODEL`, then re-index. Keys stay on the server. Details:
[docs/ARCHITECTURE.md#wayzen](docs/ARCHITECTURE.md#wayzen).

## Tests

```sh
# Backend: needs a disposable PostgreSQL database with pgvector (all tables are reset)
cd backend
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/queueflow_test pytest -q
ruff check app && pip-audit -r requirements.txt

# Frontend
cd frontend && npm run lint && npm run typecheck && npm test && npm run build

# Browser end-to-end walkthrough against a running stack
npm install --no-save playwright && npx playwright install chromium
ADMIN_EMAIL=... ADMIN_PASSWORD=... node e2e/run.mjs http://localhost:8080
```

Results recorded for this release: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Limits (honest summary)

Payments are not processed (hotel totals and fees are payable at the venue). Email is
used only for password reset and only when SMTP is configured; there is no SMS.
Generated Wayzen answers were exercised with a scripted test model, not a live LLM.
The Docker images and the EC2 guide were not executed in the environment used for
this release. See [docs/SECURITY.md](docs/SECURITY.md) and
[docs/VERIFICATION.md](docs/VERIFICATION.md) for the full list.
