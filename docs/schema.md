# Database Schema

All tables use UUID primary keys (stored as `varchar(36)`, generated client-side by
SQLAlchemy) and `TIMESTAMPTZ` for all timestamps.

## `users`
| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| email | varchar(255) | unique, indexed |
| hashed_password | varchar(255) | bcrypt hash, never plaintext |
| full_name | varchar(255) | |
| role | enum | `CUSTOMER` \| `STAFF` \| `ADMIN` |
| is_active | boolean | default true |
| created_at, updated_at | timestamptz | |

## `services`
| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| name | varchar(255) | |
| description | text | nullable |
| is_active | boolean | |
| created_by | varchar(36) FK → users.id | nullable |
| created_at, updated_at | timestamptz | |

## `queues`
| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| service_id | varchar(36) FK → services.id | indexed |
| name | varchar(255) | |
| status | enum | `OPEN` \| `PAUSED` \| `CLOSED` |
| next_token_number | integer | monotonic counter, advanced under row lock |
| current_serving_number | integer | nullable |
| created_at, updated_at | timestamptz | |

Composite index on `(service_id, status)` for the customer-facing "open queues for this
service" query.

## `tickets`
| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| queue_id | varchar(36) FK → queues.id | indexed |
| customer_id | varchar(36) FK → users.id | indexed |
| token_number | integer | sequential per queue |
| token_label | varchar(16) | e.g. `A047` |
| status | enum | `WAITING` → `CALLED` → `SERVING` → `SERVED`, or `SKIPPED` / `CANCELLED` |
| called_at, serving_started_at, served_at, skipped_at, cancelled_at | timestamptz | nullable, set on the matching transition |
| created_at | timestamptz | indexed — creation timestamp; FIFO uses token_number |

Composite indexes on `(queue_id, status)` and `(customer_id, status)` — the two hot paths
(staff's "who's waiting" and a customer's "do I already have an active ticket here").

## `appointments`
| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| customer_id | varchar(36) FK → users.id | indexed |
| service_id | varchar(36) FK → services.id | indexed |
| scheduled_time | timestamptz | |
| status | enum | `SCHEDULED` \| `CHECKED_IN` \| `COMPLETED` \| `CANCELLED` \| `NO_SHOW` |
| notes | text | nullable |
| created_at | timestamptz | |

## `service_records`
Historical record written every time a ticket is served — this is what wait-time estimation
reads from. One row per ticket.

| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| ticket_id | varchar(36) FK → tickets.id | unique |
| queue_id | varchar(36) FK → queues.id | indexed |
| service_id | varchar(36) FK → services.id | indexed |
| wait_seconds | integer | `serving_started_at - created_at` |
| service_seconds | integer | `served_at - serving_started_at` |
| outcome | enum | currently always `SERVED` (skips don't generate a record) |
| created_at | timestamptz | indexed — the "last 50 records" query orders by this |

## `notifications`
| Column | Type | Notes |
|---|---|---|
| id | varchar(36) PK | |
| user_id | varchar(36) FK → users.id | indexed |
| ticket_id | varchar(36) FK → tickets.id | nullable |
| type | enum | `TURN_APPROACHING` \| `CALLED` \| `QUEUE_UPDATE` \| `SYSTEM` |
| message | varchar(500) | |
| is_read | boolean | |
| created_at | timestamptz | indexed |

Currently written (e.g. on "call next") but not yet read back by a dedicated notifications
endpoint — the frontend surfaces the equivalent state directly from the live WebSocket
payload and ticket detail response instead. The table exists so a notifications inbox/read
receipts feature can be added without a schema change.
