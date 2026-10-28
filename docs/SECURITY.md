# Security

QueueFlow is not "unhackable". This page lists the controls that exist, how each was
verified, and the risks that remain.

## Controls

| Area | Control | Verified by |
|------|---------|-------------|
| Passwords | Argon2id (argon2-cffi defaults); legacy bcrypt hashes upgraded on login; 10–128 chars, letter + digit, common-password and email-name checks | `test_auth.py` |
| Sessions | Random 256-bit token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` in production); only an HMAC of it is stored; 12 h absolute and 2 h idle expiry; rotated on login | `test_auth.py`, E2E (cookie is HttpOnly, nothing in localStorage) |
| Revocation | Logout, "log out of all devices", password change (other sessions), password reset (all), role change (all) | `test_auth.py`, `test_operations.py` |
| CSRF | Double-submit token (`qf_csrf` cookie + `X-CSRF-Token` header) on every unsafe request with a session; Origin allowlist on all unsafe requests | `test_auth.py` |
| Brute force | 20 auth requests/min/IP; 5 failed logins per account per 15 min; reset requests 3/15 min/email; in-process fallback if Redis is down | `test_auth.py` |
| Password reset | Random single-use token, 30-minute expiry, digest stored; identical response for unknown emails; never logged outside `ENV=development` | `test_auth.py` |
| Authorization | Server-side RBAC (customer/staff/admin); staff limited to assigned venues; admins cannot remove their own access; public registration cannot set a role | `test_operations.py`, `test_authorization.py` |
| Object level | Bookings, reservations, notifications, chats and Wayzen actions are filtered by owner; others' references return 404 | `test_bookings.py`, `test_hotels.py`, `test_wayzen.py`, E2E |
| Input | Pydantic schemas with `extra="forbid"` (no mass assignment); LIKE wildcards escaped; ORM / bound parameters only; 1 MB request limit (app and nginx) | `test_auth.py`, `test_bookings.py` |
| Consistency | Row locks, exclusion constraint against overlapping bookings, guarded inventory updates, idempotency keys | concurrency tests in `test_bookings.py`, `test_hotels.py` |
| WebSockets | Session cookie required, Origin allowlist, 5 sockets/user, session re-checked every 30 s, only `ping` frames accepted, private per-user channels | `test_operations.py` |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP; CSP on the SPA (`script-src 'self'`); `no-store` on API responses | `test_auth.py`, manual curl, E2E (no CSP violations) |
| Errors | Generic 500/409/503 bodies; validation errors without internals | handlers in `main.py` |
| AI | Allowlisted typed tools; tools run as the user through normal services; no SQL/shell/code tools; actions need UI confirmation (atomic, single use); retrieved text escaped and labelled untrusted; access control in the retrieval SQL; no secrets in prompts; per-user chat rate limit; emergency notice independent of the model | `test_wayzen.py` (scripted model incl. prompt injection, unknown tools, IDOR attempts) |
| Infrastructure | Only the frontend port is published; DB/Redis/backend on 127.0.0.1; app connects as a non-superuser role; non-root containers with `no-new-privileges`; secrets only in `.env` (git-ignored) | Compose config review; DB role scripts tested locally |
| Supply chain | `pip-audit` and `npm audit` in CI; ruff with bandit (`S`) rules | 0 known vulnerabilities at release time |

## Remaining risks and follow-up

1. **HTTP-only demo deployments** send credentials in clear text and cannot use
   `Secure` cookies. Use HTTPS (see `AWS_EC2.md`) before real users.
2. **Cross-site hosting** (e.g. SPA and API on different Render domains) needs
   `COOKIE_SAMESITE=none` + HTTPS and was not tested; same-origin via nginx is the
   supported setup.
3. **Email/SMS:** password reset needs SMTP; without it users cannot self-reset.
   SMS is not implemented. Email delivery was not tested against a real server.
4. **LLM behaviour:** the security model does not rely on the model, but answer
   quality and refusal behaviour with a real provider were not evaluated here.
5. **Rate limits** are per IP and fixed-window; distributed attacks need an upstream
   WAF. The general limiter fails open to per-process counting if Redis is down.
6. **No account lockout notifications, MFA, or audit-log UI beyond the admin API.**
7. **Swagger UI** at `/docs` is public (as in 1.x) and loads assets from jsdelivr.
   Restrict it at the proxy in production if the API surface should not be listed.
8. Recommended next steps: external penetration test, dependency update policy,
   container image scanning, centralised logs and alerting, backup restore drills.
