# Verification record (2026-10-28)

Environment: Linux container with PostgreSQL 16.x + pgvector + btree_gist, Redis 7,
Python 3.12, Node 22, nginx 1.24 using the repository's `frontend/nginx.conf`
(only the upstream address and root path substituted), Chromium via Playwright.
Docker Hub was blocked from that environment, so **container images were not built
or run**; services ran natively with the same configuration.

## Results

| Check | Result |
|-------|--------|
| Backend tests (`pytest`, real PostgreSQL) | **137 passed**, 0 failed |
| Backend lint (`ruff check app`, incl. bandit `S` rules) | clean |
| Python dependency audit (`pip-audit`) | 0 known vulnerabilities (after upgrading certifi, dnspython) |
| Alembic | upgrade → `alembic check` (no drift) → downgrade → re-upgrade, all succeeded; upgrade also succeeded as the non-superuser `queueflow_app` on a 1.x-style database after `upgrade-existing-volume.sql` |
| Frontend `tsc -b`, `oxlint` | clean (0 errors) |
| Frontend tests (Vitest + Testing Library) | **16 passed** |
| npm audit | 0 vulnerabilities |
| Production build | succeeded |
| Browser E2E (`e2e/run.mjs`, 1280 px + 375 px) | **16/16 steps passed** |
| API smoke test (`scripts/smoke_test.py`) via nginx | all checks passed |
| Seed and ingestion idempotence | second run: 0 created / 24 unchanged |
| Retrieval evaluation (12 questions, offline embedder, k=5) | hit@1 0.75, hit@5 1.00, MRR 0.836 |
| Multi-instance realtime | booking made through backend instance A delivered a notification to a WebSocket held by instance B (via Redis pub/sub) |
| `docker compose config` | valid |
| nginx | CSP present, no CSP violations in the SPA or `/docs`, 2 MB body → 413, WebSocket upgrade works |

## What the tests cover

- **Auth:** registration validation and policy, duplicate emails, Argon2id, bcrypt
  upgrade, generic login errors, CSRF, foreign Origin, logout revocation, session
  rotation, expiry and idle timeout, password change and reset (single use, no
  enumeration), brute-force lockout, route rate limits, audit events, headers, body limit.
- **Bookings:** search/filters, doctors shown only where configured, end-to-end hospital
  booking, sequential per-doctor tokens, "any available", invalid requests (wrong doctor,
  other venue's service, off-grid time, naive time, past, beyond horizon), double booking,
  customer overlap, idempotency, object-level access, cancellation freeing slots without
  reusing tokens, cut-off policy, rescheduling token rules, shop staff authorisation,
  service durations, **6 concurrent customers on one slot (exactly 1 wins)**,
  **5 concurrent bookings get unique tokens**, exclusion constraint enforced by PostgreSQL.
- **Hotels:** server pricing and taxes, occupancy filtering, client price ignored, invalid
  stays, last-room inventory, **6 concurrent attempts on the last room (exactly 1 wins)**,
  idempotency, free vs late cancellation fees and inventory release, atomic modification,
  isolation.
- **Operations:** venue-scoped staff access, start-next, one visit in progress, live
  estimates, delay notifications de-duplicated, exactly one 20-minute turn alert across
  repeated recomputation, invalid transitions, paused queues, customers cannot drive staff
  actions or see other customers, authenticated private WebSockets, notification read
  ownership, admin role management and self-demotion guard, provider configuration.
- **Wayzen:** relevant retrieval, below-threshold rejection, staff/private document access
  control, index updates/versioning/removal, context escaping, limited mode, emergency
  notice, private history, booking only after explicit confirmation (and single use,
  owner only), expiry and dismissal, tool authorisation (another user's reference,
  unknown tool, invalid arguments), prompt injection from a poisoned document, hotel
  reservation with server price, provider failure fallback, chat rate limit.
- **E2E (browser):** register (with validation errors), HttpOnly cookie and empty
  localStorage, find a hospital by specialization, book a cardiology slot and get a token,
  dashboard and list, live notification, shop booking, hotel reservation with server price,
  free cancellation, reschedule and cancel, another user denied, Wayzen with sources,
  admin/staff board, mobile without horizontal scroll, no uncaught page errors.

## Not verified (requires external services or infrastructure)

- **Real LLM generation.** Tool calling and grounding were tested with a scripted test
  model. No Anthropic/OpenAI/Ollama call was made; adapter request formats follow the
  providers' public APIs but are unexercised. The `openai_compatible` embedding default
  threshold (0.30) is a starting point to tune with `python -m app.rag.evaluate`.
- **Email delivery** (SMTP) and **browser notification/sound** behaviour on real devices.
- **Docker images, Compose runtime, GitHub Actions workflow and AWS EC2 deployment.**
- **Render** deployment of 2.0.
