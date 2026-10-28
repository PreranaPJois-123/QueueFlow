# Audit of the uploaded QueueFlow archive (2026-10-28)

Method: backend run against real PostgreSQL 16 + Redis 7, frontend production
build served through the repository's nginx config, and a headless-Chromium
walkthrough of every customer page.

## What already worked (verified)

- Registration/login, walk-in service queues (join, call, serve, skip, cancel),
  generic service appointments, staff queue pages, analytics, health endpoint.
- Alembic migration on PostgreSQL; 73 backend tests (SQLite) passed.

## Problems found (root causes)

| # | Problem | Root cause |
|---|---------|------------|
| 1 | Hospitals, hotels, shops, doctors, slots, room inventory, reservations do not exist | Not implemented: the data model only has generic `services`/`queues`/`appointments` |
| 2 | No chatbot / RAG | Not implemented |
| 3 | Fresh install shows empty Services/Appointments pages | No seed or setup path besides manual staff configuration |
| 4 | Session token readable by any script on the page | JWT stored in `localStorage`; sent as a bearer header |
| 5 | Logout does not end the session | Stateless JWT, no server-side revocation |
| 6 | No password change or reset | Not implemented |
| 7 | Passwords hashed with bcrypt (72-byte limit) | Requirement is Argon2id |
| 8 | Login brute force only limited by a shared 120 req/min/IP bucket | No per-account or per-route limits |
| 9 | Turn-approaching alerts never generated; notifications only appear on refresh | `TURN_APPROACHING` enum exists but nothing creates it; no per-user realtime channel |
| 10 | Real-time fan-out works on one process only | In-memory WebSocket manager |
| 11 | Tests cannot detect locking or constraint bugs | Suite runs on SQLite |
| 12 | Browser console errors / third-party request on every page | Font loaded from Google Fonts at runtime |
| 13 | No security headers, request-size limits or CSRF protection | Not implemented |
| 14 | Database user is the PostgreSQL superuser | Single credential in Compose |

Fixes are listed in `docs/CHANGES.md`; remaining limitations in `docs/SECURITY.md`.
