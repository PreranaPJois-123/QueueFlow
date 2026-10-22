# QueueFlow product behavior

## Customer workspace

The dashboard reads the signed-in customer's real tickets, appointments and in-app
notifications. Services display real queue counts, current status and estimates.
Joining returns the assigned ticket and opens its detail page. Multiple active
tickets can be selected independently; history remains available. Waiting tickets
can be cancelled after confirmation. The profile supports validated name changes;
email and role changes remain administrator-controlled.

## Staff workspace

Staff and administrators can configure services, open queues, call the next FIFO
ticket, explicitly start service, complete or skip visits, and pause/resume queues.
Closing requires an empty queue and is permanent. Customer details and history are
available only to staff/admin endpoints. Public queue snapshots contain no customer
names or contact details. The appointment console filters by customer, service,
status and date period. Analytics aggregate actual ticket outcomes and completed
service records, with a seven-day UTC trend and an explicitly labelled current
queue-load snapshot.

## Appointments

Reservations last 30 minutes. The availability endpoint offers half-hour starts
within the selected local calendar day; it converts the supplied local UTC offset
to UTC. There are no configured business hours in the existing schema, so the
calendar supports continuous appointment hours. The existing arbitrary-time API
contract is preserved; every booking still validates timezone, future time, active
service, a 90-day horizon, and overlapping active reservations for either the
customer or service. Both SCHEDULED and CHECKED_IN reservations block overlaps.
Cancelled/completed/no-show reservations release the time.

Booking transactions lock the customer row and then the service row in a fixed
order. PostgreSQL serializes concurrent writes across both shared resources.
Availability is advisory: creation rechecks conflicts while holding the locks.
No schema changes or destructive data migrations are needed.

## Wait prediction

`app/services/prediction.py` is isolated from mutation/state-machine logic. It uses
up to 200 real, positive-duration completed records for the same queue. Before 20
samples, the recent mean is used, or DEFAULT_AVG_SERVICE_MINUTES for a new queue.
At 20 samples, nearest-neighbour regression selects similar cyclical UTC hour and
weekday features and predicts their median service duration. Position multiplied
by that duration produces an estimated wait. This is a transparent small-data
baseline model, not a validated production forecast. No accuracy score is claimed.
Pauses and unpredictable service delays can change the actual wait.

## Updates and recovery

Ticket and queue control pages subscribe to queue snapshots over WebSockets.
Heartbeat snapshots confirm liveness; stale connections close and retry with
backoff. LIVE / RECONNECTING / OFFLINE indicators describe connection state.
Authenticated HTTP refreshes provide recovery if broadcasts are missed. Queue
lists refresh every five seconds; other summaries normally refresh every 15.
Failed refreshes retain prior data and display an explicit stale-data error with
retry. The backend remains single-process; multi-replica fan-out needs Redis pub/sub.

## Security and operation

Existing JWT checks, customer ownership, staff/admin guards, Redis rate limiting,
queue locks, migration startup and Render origin configuration are preserved.
Public signup creates CUSTOMER accounts only. Account bootstrap remains explicit;
no demo data is created in production. Empty pages represent absent real records
and include guidance to publish services/open queues/book visits.
