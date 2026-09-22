import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, extractErrorMessage } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { TicketStatusBadge } from '../../components/Badge'
import { useQueueSocket } from '../../lib/useQueueSocket'
import type { Ticket, TicketDetail, Appointment } from '../../types'

export default function CustomerDashboard() {
  const { user } = useAuth()
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [appointments, setAppointments] = useState<Appointment[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activeTicket = tickets?.find((t) => t.status === 'WAITING' || t.status === 'CALLED' || t.status === 'SERVING')
  const { state: liveQueue } = useQueueSocket(activeTicket?.queue_id ?? null)

  async function loadTickets() {
    try {
      const { data } = await api.get<Ticket[]>('/api/tickets/mine')
      setTickets(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function loadAppointments() {
    try {
      const { data } = await api.get<Appointment[]>('/api/appointments')
      setAppointments(data.filter((a) => a.status === 'SCHEDULED').slice(0, 3))
    } catch {
      // non-critical; dashboard still works without upcoming appointments
    }
  }

  useEffect(() => {
    loadTickets()
    loadAppointments()
  }, [])

  useEffect(() => {
    if (!activeTicket) {
      setDetail(null)
      return
    }
    api.get<TicketDetail>(`/api/tickets/${activeTicket.id}`).then((r) => setDetail(r.data)).catch(() => {})
  }, [activeTicket?.id, liveQueue])

  return (
    <AppShell variant="customer">
      <h1 className="text-xl font-semibold text-ink-900">Welcome back{user ? `, ${user.full_name.split(' ')[0]}` : ''}</h1>
      <p className="mt-1 text-sm text-ink-500">Here's where things stand right now.</p>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2">
          {tickets === null ? (
            <Skeleton className="h-48 w-full" />
          ) : activeTicket && detail ? (
            <div className="rounded-2xl border border-ink-100 bg-white p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-400">Your ticket</p>
                  <p className="token-display mt-1 text-5xl font-bold text-ink-900">{activeTicket.token_label}</p>
                </div>
                <TicketStatusBadge status={activeTicket.status} />
              </div>

              {detail.smart_alert && (
                <div className="mt-4 rounded-lg bg-amber-100 px-4 py-3 text-sm font-medium text-amber-600">
                  Your turn is approaching. Please be ready.
                </div>
              )}

              <div className="mt-6 grid grid-cols-3 gap-4 border-t border-ink-100 pt-5 text-sm">
                <div>
                  <p className="text-ink-400">Current token</p>
                  <p className="mt-1 font-semibold text-ink-900">{detail.current_serving_label ?? '—'}</p>
                </div>
                <div>
                  <p className="text-ink-400">People ahead</p>
                  <p className="mt-1 font-semibold text-ink-900">{detail.people_ahead}</p>
                </div>
                <div>
                  <p className="text-ink-400">Estimated wait</p>
                  <p className="mt-1 font-semibold text-signal-700">~{detail.estimated_wait_minutes} min</p>
                </div>
              </div>

              <div className="mt-5">
                <div className="h-2 w-full overflow-hidden rounded-full bg-ink-100">
                  <div
                    className="h-full rounded-full bg-signal-500 transition-all"
                    style={{
                      width: `${Math.max(6, 100 - Math.min(detail.people_ahead, 10) * 10)}%`,
                    }}
                  />
                </div>
                <p className="mt-2 text-xs text-ink-400">Progress toward your turn</p>
              </div>

              <Link to="/my-ticket" className="mt-5 inline-block text-sm font-medium text-signal-700 hover:underline">
                View full ticket →
              </Link>
            </div>
          ) : (
            <EmptyState
              title="No active ticket"
              body="Join a queue to get a token and start tracking your wait."
              action={
                <Link to="/services">
                  <Button size="sm">Browse services</Button>
                </Link>
              }
            />
          )}
        </section>

        <section className="rounded-2xl border border-ink-100 bg-white p-6">
          <p className="text-sm font-semibold text-ink-900">Upcoming appointments</p>
          {appointments === null ? (
            <Skeleton className="mt-3 h-20 w-full" />
          ) : appointments.length === 0 ? (
            <p className="mt-3 text-sm text-ink-400">No upcoming appointments.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-3">
              {appointments.map((a) => (
                <li key={a.id} className="rounded-lg border border-ink-100 px-3 py-2 text-sm">
                  <p className="font-medium text-ink-800">{new Date(a.scheduled_time).toLocaleString()}</p>
                  {a.notes && <p className="text-ink-400">{a.notes}</p>}
                </li>
              ))}
            </ul>
          )}
          <Link to="/appointments" className="mt-4 inline-block text-sm font-medium text-signal-700 hover:underline">
            Manage appointments →
          </Link>
        </section>
      </div>
    </AppShell>
  )
}
