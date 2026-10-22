# QueueFlow

Real-time queue and appointment management with React/Vite, FastAPI, PostgreSQL,
Redis and WebSockets. Customers register, join queues and track tickets; staff
manage services, queues and ticket transitions.

**Deployment:** The frontend is hosted at
[queueflow-frontend-wy9t.onrender.com](https://queueflow-frontend-wy9t.onrender.com).
See [Render deployment](docs/DEPLOYMENT.md) for the initial administrator and
service setup required before customers can book or join a queue.

## Architecture

The static frontend calls the backend's public HTTPS origin. WebSockets use the
same host with WSS. PostgreSQL is the authoritative queue/ticket store; Redis
provides fixed-window rate limits. Queue mutations acquire a queue row lock before
ticket locks, then commit and publish state. The WebSocket manager supports one
backend process/instance. Production startup applies Alembic migrations.

See [product behavior](docs/PRODUCT.md) for customer/staff features, appointment rules, historical prediction and live-update recovery.

## Features and access

- Customer registration/login, active service browsing, joining and cancelling
  waiting tickets, ticket history, queue position and wait estimates.
- Staff-only service/queue management, calling, starting service, completing and skipping tickets,
  pause/resume, and closing queues once active tickets are resolved.
- Appointment availability, overlap prevention and cancellation with timezone, active-service and future-time checks.
- Analytics from stored service records; duration runs from call to completion
  unless an explicit service-start time exists.
- WebSocket initial snapshot, broadcasts, reconnects and restricted browser origins.
- Health reports actual database/Redis reachability and returns HTTP 503 on failure.
- Public registration cannot grant staff/admin roles. Trusted operators provision
  staff using `python -m app.provision_user`; see deployment notes.

## Local development

Requires Python 3.12, Node 22, PostgreSQL and Redis (or Docker Compose).
Copy `backend/.env.example` to `backend/.env`, set development database/Redis
connections and a generated JWT secret, then:

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In `frontend`, copy `.env.example` to `.env`, then run `npm ci` and `npm run dev`.
Local example URLs are development-only. Production builds require `VITE_API_URL`;
Render builds require a public HTTPS origin. Never commit populated `.env` files.

<<<<<<< HEAD
### Docker Compose

```sh
cp .env.example .env    # then fill JWT_SECRET_KEY and POSTGRES_PASSWORD (openssl rand -hex 32 / -hex 24)
docker compose up -d --build
curl http://localhost:8080/api/health
```

The app is served at http://localhost:8080. The frontend nginx proxies `/api`
(including WebSockets) to the backend, so the browser uses a single origin.
PostgreSQL, Redis and the backend bind to `127.0.0.1` only. Required variables:
`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`; optional: `VITE_API_URL`/`CORS_ORIGINS`
(public origin, default `http://localhost:8080`), `FRONTEND_PORT`,
`INITIAL_ADMIN_EMAIL`/`_NAME`/`_PASSWORD`. If you have a `postgres_data` volume from
an earlier version, set `POSTGRES_PASSWORD=queueflow` (the old built-in value) or
recreate the volume.

**AWS EC2:** see [docs/AWS_EC2.md](docs/AWS_EC2.md) for a single-instance deployment
with least-privilege security groups, backups and reboot recovery. End-to-end
check against any deployment: `scripts/smoke_test.py`.
=======
For the optional local Docker stack, copy root `.env.example` to `.env` and set a
real `JWT_SECRET_KEY`, then run `docker compose up --build`. Docker images were built successfully in GitHub CI; the full Compose runtime
has not been exercised.
>>>>>>> 53aa3faa382e169f79fb911f954a11c4a42a30dc

## Testing and CI

```sh
cd backend
pytest -q
```

Tests default to isolated in-memory SQLite. Set `TEST_DATABASE_URL` only to a
**disposable test database**: fixtures reset its tables. SQLite tests do not prove
PostgreSQL locking or migration behavior. `ENV=test` bypasses rate limits, so real
Redis throttling was verified separately using an actual local HTTP server.

Frontend: `npm ci`, `npm run lint`, and `VITE_API_URL=BACKEND_ORIGIN npm run build`.
Lint and TypeScript checks are run before publication.

<<<<<<< HEAD
Verified on 2026-10-22 against real PostgreSQL 16 and Redis 7 (run natively; the
container images could not be pulled in that environment): Alembic migration
and idempotent re-run, admin bootstrap, `/api/health`, the full
`scripts/smoke_test.py` workflow both directly and through the nginx proxy
config (register/login, role-escalation rejection, staff service/queue
creation, join, call-next, serve, ticket history), WebSocket upgrade through the
proxy with foreign origins rejected (403), data retained across a database and
backend restart, and `pytest` (73 passed, 1 skipped). `docker compose config`
validates; the Compose containers themselves were not run in that session.

=======
>>>>>>> 53aa3faa382e169f79fb911f954a11c4a42a30dc
`.github/workflows/ci.yml` adds PostgreSQL/Redis service containers, migration
upgrade/check/downgrade/re-upgrade, backend tests, frontend checks and Docker image
builds. Earlier repairs passed that workflow, including PostgreSQL and both Docker builds.
The current update must pass its own workflow run; see [verification](docs/VERIFICATION.md). It contains no deployment credentials.

## API and schema

Interactive API documentation is at `/docs` on the backend. Key prefixes are
`/api/auth`, `/api/services`, `/api/queues`, `/api/tickets`, `/api/staff`,
`/api/appointments`, `/api/analytics`, `/api/product` and `/api/health`.
WebSockets subscribe at `/api/queues/{queue_id}/ws`.
[Schema details](docs/schema.md) describe the seven tables.

## Limits

Local checks and the existing live frontend alone do not verify every production
workflow. The included free Render plans are for a preview and
must be replaced with approved paid plans for an ongoing production service.
JWTs are stored in browser local storage; logout clears that copy, without
server-side revocation. Notifications are in-app only. Real-time fan-out is
single-process. Browser end-to-end testing remains outstanding.
