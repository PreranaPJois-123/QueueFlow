# Deployment

No live URL ships with this project — see the README's [Limitations](../README.md#limitations--whats-not-verified)
for why. This document is the exact playbook to deploy it for real.

## Why Render or Railway

QueueFlow needs three things a deployment target must support well:
1. **Persistent PostgreSQL** (not ephemeral/serverless-reset storage)
2. **Long-lived WebSocket connections** (the real-time queue updates depend on this —
   some serverless/edge platforms kill connections after a short timeout)
3. **A free or low-cost tier** for a portfolio project

Render and Railway both check all three boxes and both deploy directly from a Dockerfile,
which this project already has. Fly.io is a reasonable third option if you want more control
over region placement.

## Render — step by step

1. Push this repository to GitHub.
2. In the Render dashboard: **New → PostgreSQL**. Note the internal connection string.
3. **New → Redis** (Render's managed Redis, or Upstash if you prefer). Note the connection string.
4. **New → Web Service**, connect the repo, set:
   - Root directory: `backend`
   - Environment: Docker
   - Add env vars: `DATABASE_URL`, `REDIS_URL` (from steps 2–3), `JWT_SECRET_KEY` (generate
     with `openssl rand -hex 32`), `CORS_ORIGINS` (the frontend URL from step 6, once known —
     you can update this after step 6), `ACCESS_TOKEN_EXPIRE_MINUTES=1440`,
     `RATE_LIMIT_PER_MINUTE=120`, `SMART_ALERT_THRESHOLD=3`, `DEFAULT_AVG_SERVICE_MINUTES=5`
   - Render auto-detects the `HEALTHCHECK` in the Dockerfile for its own health checks
5. Deploy. The container runs `alembic upgrade head` automatically on boot — no manual
   migration step.
6. **New → Static Site** (or a second Web Service if you'd rather run nginx in Docker), connect
   the same repo:
   - Root directory: `frontend`
   - Build command: `npm ci && npm run build`
   - Publish directory: `dist`
   - Env var: `VITE_API_URL` = the backend URL from step 5 (must be set **before** build —
     Vite bakes it into the static bundle)
7. Go back to the backend service and update `CORS_ORIGINS` to the frontend's actual URL.
8. Verify: `curl https://<backend-url>/api/health` should return
   `{"status": "healthy", "database": "up", "redis": "up"}`.

## Railway — step by step

1. Push this repository to GitHub.
2. **New Project → Deploy from GitHub repo**.
3. **New → Database → PostgreSQL** in the same project (Railway wires `DATABASE_URL`
   automatically if you reference it as a variable).
4. **New → Database → Redis** similarly.
5. Add a service for `backend/` (Railway auto-detects the Dockerfile). Set env vars as in
   the Render steps above, referencing the Postgres/Redis services' connection variables.
6. Add a service for `frontend/` the same way, with `VITE_API_URL` set as a build-time
   variable pointing at the backend service's public URL.
7. Update `CORS_ORIGINS` on the backend once the frontend's public URL is known.
8. Verify `/api/health` as above.

## What "done" looks like

After either path, confirm the full flow works against the real deployment:
1. Register a staff account, then a customer account (two browser sessions or incognito).
2. As staff: create a service, create a queue.
3. As customer: join the queue, confirm a token appears.
4. As staff: click "Call next" — confirm the customer's dashboard updates **without a
   refresh** within a second or two (this is the WebSocket path — if it doesn't work, check
   that your platform isn't proxying WebSocket upgrades incorrectly, which is the most common
   failure mode here).
5. Mark the ticket served, then check `/api/analytics` as staff shows the served count.
