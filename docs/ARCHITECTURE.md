# Architecture

QueueFlow is a modular monolith: one FastAPI service, one React SPA, PostgreSQL as
the source of truth and Redis for coordination.

```
Browser ──HTTPS/HTTP──▶ nginx (non-root, :8080)
                          │  /            static SPA (React)
                          │  /api/*       reverse proxy, incl. WebSocket upgrade
                          ▼
                 FastAPI backend (uvicorn, :8000, private)
          ┌──────────────┼──────────────────────┬──────────────────┐
   auth & sessions   booking engine        realtime hub        Wayzen (RAG)
   (cookies, CSRF)   (slots, tokens,       (user sockets,      retrieve → generate
                      inventory, queues)    queue monitor)      → allowlisted tools
          │              │                      │                  │
          ▼              ▼                      ▼                  ▼
   PostgreSQL 16  (all records, pgvector chunks, audit)     Redis 7 (rate limits,
                                                            pub/sub, monitor lock)
                                                            LLM / embedding API (optional)
```

## Backend layout

| Path | Responsibility |
|------|----------------|
| `app/core/` | config, DB engine, sessions/CSRF, Argon2 hashing, rate limiting, security middleware |
| `app/models/models.py` | users, sessions, reset tokens, notifications, audit events, legacy walk-in queues |
| `app/models/venues.py` | venues, specializations, offerings, providers, schedules, queue days, bookings, room types, inventory, reservations |
| `app/models/assistant.py` | knowledge documents, chunks (pgvector), chat sessions/messages, pending actions |
| `app/services/booking/` | `slots` (availability), `appointments` (book/cancel/reschedule), `queue_ops` (estimates, alerts, staff actions), `hotels` (quotes, inventory, reservations) |
| `app/services/realtime.py`, `notify.py` | post-commit event publishing over Redis, deduplicated notifications |
| `app/rag/` | `chunking`, `embeddings`, `store` (retrieval + context), `ingest`, `llm` adapters, `tools`, `assistant`, `evaluate` |
| `app/api/` | thin routers: `auth`, `venues`, `bookings`, `operations`, `admin`, `notifications`, `wayzen` (+ legacy queue routers) |

## Booking engine

**Slots.** Providers (doctors or shop staff) have weekly windows in the venue's
timezone. Slots for a service start at the window opening and step by the service
duration. A slot is offered if it is after the minimum notice, inside the booking
horizon, and does not overlap any active booking of that provider.

**Booking transaction.** Lock the provider row → re-validate the slot against current
bookings → reject overlaps with the customer's own appointments → lock (or create)
the provider's `queue_days` row for that date → issue the next token → insert. A
PostgreSQL exclusion constraint (`btree_gist`, `tstzrange &&`) independently forbids
overlapping active bookings for a provider, and `(queue_day_id, token_number)` is
unique. Retried requests with the same `Idempotency-Key` return the original booking.

**Token policy.** One queue per provider per venue-local date. Tokens `<PREFIX>-001`,
`-002`... are issued in booking order and never reused. Customers are served in
appointment-time order. Rescheduling within the same queue keeps the token; another
date or provider issues a new one.

**Hotel inventory.** `room_inventory(room_type, night, booked)`. Reserving locks the
room type, then per night runs `UPDATE ... SET booked = booked + n WHERE booked + n <= total`;
any full night aborts the whole transaction. Prices are computed server-side with
`Decimal` (rate × nights × rooms + tax, half-up rounding). Modifications release and
re-reserve in one transaction, so a failed change leaves the original intact.

**Dates.** Instants are stored as UTC `timestamptz`; `service_date` and hotel
check-in/out are venue-local calendar dates. The UI formats times in the venue's
timezone, not the browser's.

## Realtime and notifications

* Every state change computes live estimates **inside the same transaction** and
  queues events on the SQLAlchemy session; they are published to Redis
  (`qf:user:<id>`) only **after commit**. Each backend instance subscribes to `qf:*`
  and forwards events to its own sockets, so multiple instances work.
* `/api/ws` is authenticated with the session cookie, checks the Origin, limits five
  sockets per user, re-validates the session every 30 s, and only accepts `ping`.
  The SPA reconnects with exponential backoff and polls every 30 s while disconnected.
* **Wait estimate:** start from the in-progress visit's expected end, then add each
  earlier booking's duration (never before its scheduled time plus any announced
  delay). Durations are the median of the provider's last 30 completed visits for that
  service once 5 exist, otherwise the configured duration.
* **Turn alert:** when the estimate first reaches ≤ 20 minutes (`TURN_ALERT_MINUTES`),
  one notification is inserted with dedupe key `turn:<booking>:<slot>`
  (`ON CONFLICT DO NOTHING`). If the estimate rises and falls again there is no second
  alert; rescheduling creates a new key. A background monitor (one instance at a time,
  via a Redis lock) recomputes every minute, because time passing changes estimates.
* Sound and browser notifications are opt-in per user; a visible toast is always shown.

## Wayzen

**Pipeline.** Markdown help articles (`backend/knowledge/*.md`, with access level in
front matter) and generated documents for every active venue and specialization →
normalisation → heading-aware chunking (≤ 900 chars) → embeddings → `document_chunks`
(pgvector). Ingestion is incremental by content hash; versions increment; documents
for removed or deactivated sources are deleted. Admin edits re-index the venue in the
background; `python -m app.rag.ingest` runs on container start.

**Retrieval.** Query embedding → cosine search in SQL with the access filter applied
in the same query (public; staff-only for STAFF/ADMIN; private only for the owner) →
score threshold → at most two chunks per document → bounded context (6,000 chars)
with all angle brackets escaped so documents cannot break out of their block.
Re-ranking is not used: the corpus is small and the threshold plus per-document
diversity were sufficient in evaluation.

**Embedding providers.** `local` is an offline hashed bag-of-words embedding (unigrams
and bigrams, 1,024 dimensions): it matches words, not meaning, and needs no download.
`openai_compatible` calls any `/embeddings` API for semantic retrieval. Chunks record
their model id, and retrieval never mixes models.

**Generation.** With `LLM_PROVIDER` set, the model receives a fixed system prompt, the
last ten turns and the retrieved documents marked as untrusted data, and may call
eight allowlisted tools (search venues, venue details, free slots, hotel quotes, the
user's own bookings, and three *prepare* tools). It cites sources as `[S1]`; only
cited sources are returned. Up to five tool rounds, 30 s timeout, two retries.

**Actions.** Prepare tools re-check availability and store a `pending_actions` row
with a server-built summary (including server prices). Nothing is booked until the
user presses **Confirm** in the UI, which calls a CSRF-protected endpoint that
atomically claims the action (single use, 15-minute expiry) and runs the same booking
service with the action id as idempotency key. The model has no tool that can confirm.

**Limited mode.** Without a provider, Wayzen returns the cited help articles and says
generation is off. A deterministic emergency notice is prepended whenever a message
mentions emergency symptoms.

**Evaluation.** `python -m app.rag.evaluate` reports hit@1, hit@k and MRR over
`knowledge/eval/questions.json`. Every answer logs its retrieved chunk ids, scores,
tool calls, model and latency in `chat_messages`.
