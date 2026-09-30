# QueueFlow verification — 2026-09-30

Source baseline: GitHub main and uploaded ZIP at
`360ba2573deb74ecd05767a7baa42830e48d0e04`.

## Executed locally

- Backend regression suite: 73 passed, one PostgreSQL-only concurrency test skipped
  under SQLite; two upstream TestClient deprecation warnings.
- Regression coverage includes customer/staff authorization, JWT validation, FIFO
  transitions, duplicate joins, ownership, pause/resume/close, appointment future
  times and overlaps, available slots, profile updates, notifications, analytics,
  calculated/learned predictions, WebSocket snapshots, heartbeat and reconnects.
- Frontend lint: passed with no warnings/errors.
- TypeScript and Vite production build: passed, with the actual configurable
  Render backend HTTPS origin.
- Python dependency consistency (`pip check`): passed.
- PostgreSQL migration SQL generation: passed. Models and database schema are
  unchanged by this update, so no new migration is required.

## GitHub CI and live checks

Commit `be51b613dbc6512e21a9df5557dffabaeb823055` passed GitHub Actions run
[36712198589](https://github.com/PreranaPJois-123/QueueFlow/actions/runs/36712198589):
73 tests passed against PostgreSQL, including the concurrent booking and duplicate
join test; migration upgrade/check/downgrade/re-upgrade and both Docker builds
passed. A follow-up adds a future-appointment no-show guard and page metadata;
its workflow result is checked separately after publication.

The live backend returned HTTP 200 with database and Redis both up. The new
`/api/product/queues` endpoint returned HTTP 200 after deployment. The live
frontend served the matching built asset; browser inspection verified the landing
page and a logged-out dashboard redirect to login. No application console errors
were observed on those pages (browser-extension messages are unrelated).

## External verification gates

The existing GitHub Actions workflow runs PostgreSQL/Redis-backed tests, migration
upgrade/check/downgrade/re-upgrade and both Docker builds after publication. The
new concurrency test specifically verifies concurrent appointment reservations
and duplicate queue joins under PostgreSQL row locks. Local SQLite cannot prove
these locks, and Docker is unavailable in the local runtime.

The browser cannot open the local preview URL in this environment. Authenticated
browser workflows have not been claimed as verified. The Render dashboard in the
current browser requires sign-in; deployment and current live health are reported
separately after publication rather than inferred from this document.

## Operational limits

- A new database has no fabricated services, customers or history. Staff must
  publish real services and open queues before customers can use them.
- Appointment reservations are 30 minutes with continuous hours; business-hour
  calendars and staff-specific capacities are not configured in the schema.
- Prediction uses real history and is explicitly labelled. No accuracy claim is
  made without a proper held-out evaluation dataset.
- WebSocket fan-out remains one backend process; horizontal scaling needs Redis
  pub/sub. Render free-plan cold starts can delay the first response.
- Logout clears the browser JWT; server-side token revocation is not implemented.
