# QueueFlow 2.0: changes from the uploaded archive

Problems found are listed in [AUDIT.md](AUDIT.md). Fixes, by problem:

| # | Fix |
|---|-----|
| 1 | New venue domain: hospitals, specializations, doctors, shops, staff, weekly schedules, slot engine, appointments with queue tokens, hotel room types, nightly inventory and reservations (migration `c6d726e52bb2`) |
| 2 | Wayzen: pgvector RAG pipeline, Anthropic / OpenAI-compatible adapters, allowlisted tools, confirm-to-execute actions, limited mode, evaluation script, chat UI |
| 3 | Idempotent `python -m app.seed` with fictional venues flagged `is_sample`; `SEED_SAMPLE_DATA` for Compose |
| 4, 5 | Server-side sessions in HttpOnly cookies, HMAC-stored tokens, idle/absolute expiry, revocation, double-submit CSRF; no tokens in JavaScript storage |
| 6 | Password change and reset (single-use, expiring, non-enumerating; SMTP optional) |
| 7 | Argon2id with transparent upgrade of bcrypt hashes; stronger password policy |
| 8 | Per-route and per-account login limits with in-process fallback |
| 9 | Durable, de-duplicated notifications; 20-minute turn alerts from live estimates; delay and "your turn" alerts; per-user authenticated WebSocket; notification centre; opt-in sound/browser alerts |
| 10 | Redis pub/sub fan-out (multi-instance); background queue monitor with a Redis lock |
| 11 | Test suite moved to real PostgreSQL; new concurrency tests |
| 12 | Fonts bundled locally (no third-party requests) |
| 13 | Security middleware (headers, CSRF, Origin allowlist, 1 MB limit), CSP in nginx, generic error bodies |
| 14 | Least-privilege `queueflow_app` database role; upgrade script for 1.x volumes |

Other notable changes

- **Real bug fixed:** behind nginx, rate limits keyed on the proxy's address, so every
  user shared one bucket. Uvicorn now trusts proxy headers from the private network
  and nginx overwrites `X-Forwarded-For` so clients cannot spoof it.
- **Real bug fixed:** the RAG context builder escaped `</document>` but not the outer
  block tag, so a poisoned document could close the context; all markup is now escaped
  (found by `test_context_block_neutralises_breakout`).
- Postgres image switched to `pgvector/pgvector:pg16`; frontend runs on
  `nginx-unprivileged` (port 8080); containers use `no-new-privileges`.
- Dependencies: removed `python-jose`; added `argon2-cffi`, `pgvector`; upgraded
  `certifi`, `dnspython` (pip-audit findings); `npm audit fix` (vite, follow-redirects,
  source-map-js); Vitest 5.
- Design system (`components/ui.tsx`, `TokenStub`), role-aware shell with mobile menu,
  and new pages for discovery, booking, bookings, notifications, profile/security,
  staff operations and administration. Legacy walk-in pages kept.
- Unknown request fields are now rejected (422) instead of ignored; bearer tokens are
  no longer accepted.
- CI: ruff (incl. security rules), pip-audit, npm audit, typecheck, Vitest, retrieval
  evaluation, Docker builds, and a Compose + browser end-to-end job.
