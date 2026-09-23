# QueueFlow repair verification — 2026-09-22

Status: **BLOCKED — no live Render deployment verified.**

The repair is based on GitHub main `9bf895f2dcac5a7a085e697958494ea749c58915`
and the uploaded ZIP. The repository's newer database URL normalization and PORT
handling were preserved. Its missing `frontend/src/lib` files were restored from
the upload; the broad `lib/` ignore rule was corrected.

## Executed checks

| Check | Actual result |
|---|---|
| Frontend `npm ci` | Passed using the supplied lockfile |
| TypeScript + Vite production build | Passed with `RENDER=true`, `VITE_API_URL=https://api.example.com` (test value only) |
| Frontend lint | Exit 0; React hook/fast-refresh warnings remain |
| Production URL validation | Missing URL, HTTP localhost and internal-host builds correctly rejected |
| Built API client | Explicit HTTPS origin; no application `localhost:8000` fallback |
| Backend dependency install / `pip check` | Passed |
| Full backend suite | **60 passed** in full suite; one additional multi-client regression passed in follow-up (61 tests total); SQLite database, 2 upstream deprecation warnings |
| Actual local HTTP server | Uvicorn started successfully; registration, login, JWT-protected endpoint, forbidden customer write, service/queue creation, join, call, serve and analytics passed |
| Actual Redis | Redis **6.2.14** process: connection, rate-limit keys, and HTTP 429 throttling passed |
| Actual local WebSocket | Initial snapshot and join/call/serve messages passed over real sockets; two subscribers, disconnect isolation and reconnect snapshot passed in follow-up |
| Local health | HTTP 200, `status=healthy`, `database=up`, `redis=up` with SQLite and real Redis |
| Redis outage | Stopping Redis produced HTTP 503 and `redis=down` |
| CORS | Allowed-origin preflight passed; untrusted-origin preflight rejected in regression tests |
| Blueprint | Passed Render's published JSON Schema and static-site field checks |
| Migration | Alembic generated PostgreSQL upgrade SQL successfully; no real Postgres execution claimed |
| Source hygiene | Diff whitespace check passed; generated ZIP uses tracked source only |

Dependency bundles include generic localhost literals for URL parsing. These are
not QueueFlow API targets. Browser network traffic has not been observed, so the
bundle inspection is not a claim of browser-level verification.

## Repairs covered by regression tests

Public staff/admin registration is denied; UTF-8 passwords exceeding bcrypt's byte
limit return validation errors; expired and incomplete JWTs are rejected. Missing
queues/services return 404, invalid appointment times return 422, terminal
appointments cannot be cancelled again, and inactive services cannot be joined.
Queue FIFO uses the lock-protected token sequence, serving tickets block another
call, service durations use call/start time, and closing an active queue is rejected.
WebSockets send initial snapshots, validate queue existence, enforce browser origin
checks and broadcast state changes. Health tests no longer hide a Redis outage.

Frontend fixes include visible ticket status updates, completed-ticket refresh,
staff action controls after initial load, login navigation and effect-scoped socket
cleanup. These frontend changes were type-checked/built but not browser-tested.

## Not executed / remaining gates

- Render dashboard access was denied by browser approval. No resources were created
  or synced, no deployment logs were available, and no live URLs were discovered.
- GitHub publication is separate from a local commit; see the final deployment
  report for the actual push result.
- Docker was unavailable. System PostgreSQL installation failed because this
  environment could not change process user/group IDs. Real Postgres connections,
  migration execution, concurrent row locking and Docker builds remain unverified.
- The new GitHub Actions workflow defines those Postgres/Redis/Docker checks but
  has not been run here. CI definitions are not successful CI results.
- The backend's actual frontend CORS origin and Render-injected Vite API URL must
  be checked after Blueprint sync. Existing Blueprint `sync: false` values need
  explicit service configuration.
- No production staff/admin account was provisioned. A privileged CLI is supplied.
- No real-browser frontend test, logout/refresh/navigation test, Render WSS/TLS
  test, or live application test was performed.
- Free Render plans were preserved; approval of appropriate paid plans is needed
  before treating this as an ongoing production deployment.

The ZIP name is the requested deliverable name, not a certification that deployment
or every production check has succeeded.

## Follow-up repository and access check

GitHub main was read again and remained at the same base commit above. The GitHub
plugin is still unconnected, so the local repairs cannot be published. A renewed
Render navigation request was rejected because a saved browser permission blocks
`dashboard.render.com`. Authorize GitHub repository access and change that saved
Render browser permission to continue. These are account/access blockers; no
code change can resolve them. Docker is still unavailable.
