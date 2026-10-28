# Data model

PostgreSQL 16 with `btree_gist` and `vector`. Migrations: `backend/alembic/versions`
(`700500789b17` initial walk-in schema, `c6d726e52bb2` venues, sessions and Wayzen).
Timestamps are UTC `timestamptz`; `service_date`, `check_in`, `check_out` and
`room_inventory.night` are venue-local calendar dates. Money is `NUMERIC(10|12, 2)`.

## Accounts and security
| Table | Purpose / key constraints |
|-------|---------------------------|
| `users` | email unique; role `CUSTOMER/STAFF/ADMIN`; Argon2id hash; notification preferences |
| `user_sessions` | `token_hash` unique (HMAC of the cookie token); expiry, last seen, revoked_at |
| `password_reset_tokens` | `token_hash` unique; expires_at; used_at |
| `audit_events` | actor, action, entity, JSONB detail, IP; indexed by entity and time |
| `notifications` | per user; `dedupe_key` unique (idempotent alerts); optional booking/reservation FK |

## Venues and appointments
| Table | Purpose / key constraints |
|-------|---------------------------|
| `venues` | kind `HOSPITAL/SHOP/HOTEL`; `slug` unique; IANA timezone; `is_sample`; policy columns with CHECKs |
| `specializations` | name and slug unique |
| `offerings` | bookable service; unique (venue, name); duration 5–480 min; optional specialization and price |
| `providers` | doctor or staff member; unique (venue, token_prefix); prefix `^[A-Z0-9]{1,8}$` |
| `provider_offerings` | which provider may deliver which service (composite PK) |
| `schedules` | weekly windows; weekday 0–6; end > start; unique (provider, weekday, start) |
| `venue_staff` | staff accounts allowed to operate a venue |
| `queue_days` | one per (provider, date), unique; token counter, OPEN/PAUSED, delay minutes |
| `bookings` | reference unique; unique (queue_day, token_number); unique (customer, idempotency_key); **exclusion constraint**: no overlapping active bookings per provider; indexes on (customer, start), (queue_day, status), (venue, date) |

## Hotels
| Table | Purpose / key constraints |
|-------|---------------------------|
| `room_types` | unique (venue, name); occupancy 1–12; rate ≥ 0; total rooms |
| `room_inventory` | PK (room_type, night); `booked ≥ 0`; updated only by guarded atomic increments |
| `reservations` | reference unique; check_out > check_in; rooms 1–5; server-computed nights, subtotal, taxes, total, cancellation fee; unique (customer, idempotency_key) |

## Wayzen
| Table | Purpose / key constraints |
|-------|---------------------------|
| `knowledge_documents` | `source` unique; category; entity; `access_level` public/staff/private (private requires owner); version; content hash; embedding model |
| `document_chunks` | ordinal, heading, content, `embedding vector`, embedding model; cascade on document delete |
| `chat_sessions`, `chat_messages` | per user; messages store mode, cited sources, retrieval scores, tool calls, model, latency |
| `pending_actions` | prepared bookings/cancellations; status pending → executed/dismissed/expired/failed; expires_at |

## Walk-in queues (1.x, unchanged)
`services`, `queues`, `tickets`, `appointments`, `service_records`.
