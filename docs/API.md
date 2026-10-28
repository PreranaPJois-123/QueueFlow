# API overview

Interactive OpenAPI documentation is served at `/docs` (schema at `/openapi.json`).
All endpoints are under `/api`. Browser sessions use cookies; unsafe requests must
send `X-CSRF-Token` (value of the `qf_csrf` cookie or of `csrf_token` returned by the
session endpoints). Errors return `{"detail": "..."}` or, for validation,
`{"detail": [{"loc": [...], "msg": "..."}]}`.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /auth/register` (full_name, email, password, confirm_password) · `POST /auth/login` · `POST /auth/logout` · `POST /auth/logout-all` · `GET /auth/session` · `GET/PATCH /auth/me` (name, notification preferences) · `POST /auth/password` · `GET /auth/capabilities` · `POST /auth/password-reset/request` · `POST /auth/password-reset/confirm` |
| Catalogue (public) | `GET /venues?kind=&q=&city=&specialization=&limit=&offset=` · `GET /venues/cities` · `GET /specializations` · `GET /venues/{id}` · `GET /venues/{id}/slots?offering_id=&date=&provider_id=` · `GET /venues/{id}/rooms?check_in=&check_out=&guests=&rooms=` (server-priced quotes) |
| Appointments | `POST /bookings` (`Idempotency-Key` header supported) · `GET /bookings?scope=upcoming\|past\|all` · `GET /bookings/{reference}` (includes live queue on the visit day) · `POST /bookings/{reference}/cancel` · `POST /bookings/{reference}/reschedule` |
| Hotel | `POST /reservations` (`Idempotency-Key`) · `GET /reservations` · `GET /reservations/{reference}` · `GET /reservations/{reference}/cancellation-terms` · `POST /reservations/{reference}/cancel` · `POST /reservations/{reference}/modify` |
| Notifications | `GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all` · `WS /ws` (events: `notification`, `booking_update`) |
| Staff | `GET /ops/venues` · `GET /ops/venues/{id}/queue?date=` · `POST /ops/bookings/{id}/{check-in\|start\|complete\|no-show\|cancel}` · `POST /ops/providers/{id}/queue/{date}/next` · `POST /ops/providers/{id}/queue/{date}` (`paused`, `delay_minutes`) · `GET /ops/venues/{id}/reservations?date=` · `POST /ops/reservations/{id}/{check-in\|check-out\|no-show}` |
| Admin | `GET/POST /admin/venues` · `GET/PUT /admin/venues/{id}` · `POST /admin/venues/{id}/offerings` · `PUT /admin/offerings/{id}` · `GET/POST /admin/venues/{id}/providers` · `PUT /admin/providers/{id}` · `POST /admin/venues/{id}/room-types` · `PUT /admin/room-types/{id}` · `GET/POST /admin/venues/{id}/staff` · `DELETE /admin/venues/{id}/staff/{user_id}` · `GET /admin/users` · `PATCH /admin/users/{id}` · `GET /admin/specializations` · `GET /admin/audit` · `GET /admin/knowledge` · `POST /admin/knowledge/reindex` |
| Wayzen | `GET /wayzen/status` · `POST /wayzen/chat` · `GET /wayzen/sessions` · `GET/DELETE /wayzen/sessions/{id}` · `POST /wayzen/actions/{id}/confirm` · `POST /wayzen/actions/{id}/dismiss` |
| Walk-in queues (1.x) | `/services`, `/queues`, `/tickets`, `/staff`, `/appointments`, `/analytics`, `/product` (unchanged behaviour; now cookie-authenticated) |
| Health | `GET /health` → database, redis, assistant mode, indexed chunk count (503 if a dependency is down) |

Status codes: 201 created, 200 repeated idempotent request, 401 not signed in,
403 not allowed / CSRF / foreign origin, 404 not found or not yours, 409 conflict
(slot taken, sold out, invalid transition), 413 too large, 422 validation, 429 rate limited.
