# QueueFlow

Real-time queue and appointment management with React/Vite, FastAPI, PostgreSQL,
Redis and WebSockets. Customers register, join queues and track tickets; staff
manage services, queues and ticket transitions.

**Deployment status: blocked, not live-verified.** See
[verification evidence](docs/VERIFICATION.md) and [Render deployment](docs/DEPLOYMENT.md).
The source includes a corrected `render.yaml`; passing a build is not proof of a
working live deployment.

## Architecture

The static frontend calls the backend's public HTTPS origin. WebSockets use the
same host with WSS. PostgreSQL is the authoritative queue/ticket store; Redis
provides fixed-window rate limits. Queue mutations acquire a queue row lock before
ticket locks, then commit and publish state. The WebSocket manager supports one
backend process/instance. Production startup applies Alembic migrations.

## Features and access

- Customer registration/login, active service browsing, joining and cancelling
  waiting tickets, ticket history, queue position and wait estimates.
- Staff-only service/queue management, calling, serving and skipping tickets,
  pause/resume, and closing queues once active tickets are resolved.
- Appointment scheduling/cancellation with active-service and future-time checks.
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

For the optional local Docker stack, copy root `.env.example` to `.env` and set a
real `JWT_SECRET_KEY`, then run `docker compose up --build`. Docker runtime was not
available for verification in this repair session.

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
Lint exits successfully with existing React hook/fast-refresh warnings.

`.github/workflows/ci.yml` adds PostgreSQL/Redis service containers, migration
upgrade/check/downgrade/re-upgrade, backend tests, frontend checks and Docker image
builds. That workflow has not been run on GitHub in this session. It does not claim
a deployment and contains no deployment credentials.

## API and schema

Interactive API documentation is at `/docs` on the backend. Key prefixes are
`/api/auth`, `/api/services`, `/api/queues`, `/api/tickets`, `/api/staff`,
`/api/appointments`, `/api/analytics` and `/api/health`.
WebSockets subscribe at `/api/queues/{queue_id}/ws`.
[Schema details](docs/schema.md) describe the seven tables.

## Limits

No live frontend/backend URLs are verified. Docker and real PostgreSQL execution
remain unverified locally. The included free Render plans are for a preview and
must be replaced with approved paid plans for an ongoing production service.
JWTs are stored in browser local storage; logout clears that copy, without
server-side revocation. Notifications are in-app only. Real-time fan-out is
single-process. Browser end-to-end testing remains outstanding.
