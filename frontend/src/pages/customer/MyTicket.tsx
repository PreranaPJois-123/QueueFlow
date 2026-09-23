import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { TicketStatusBadge } from '../../components/Badge'
import { useToast } from '../../components/Toast'
import { useQueueSocket } from '../../lib/useQueueSocket'
import type { Ticket, TicketDetail } from '../../types'

export default function MyTicket() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const { push } = useToast()

  const activeTicket = tickets?.find((t) => t.status === 'WAITING' || t.status === 'CALLED' || t.status === 'SERVING')
  const { state: liveQueue, connected } = useQueueSocket(activeTicket?.queue_id ?? null)

  async function loadTickets() {
    try {
      const { data } = await api.get<Ticket[]>('/api/tickets/mine')
      setTickets(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  useEffect(() => {
    loadTickets()
  }, [])

  useEffect(() => {
    if (!activeTicket) {
      setDetail(null)
      return
    }
    api.get<TicketDetail>(`/api/tickets/${activeTicket.id}`).then((r) => {
      setDetail(r.data)
      setTickets((previous) => previous?.map((ticket) => ticket.id === r.data.ticket.id ? r.data.ticket : ticket) ?? null)
    }).catch((err) => setError(extractErrorMessage(err)))
  }, [activeTicket?.id, liveQueue])

  async function handleCancel() {
    if (!activeTicket) return
    try {
      await api.post(`/api/tickets/${activeTicket.id}/cancel`)
      push('Ticket cancelled', 'success')
      setConfirmCancel(false)
      loadTickets()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    }
  }

  const pastTickets = tickets?.filter((t) => t.id !== activeTicket?.id) ?? []

  return (
    <AppShell variant="customer">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink-900">My ticket</h1>
        {activeTicket && (
          <span className={`text-xs font-medium ${connected ? 'text-signal-600' : 'text-ink-400'}`}>
            {connected ? '● Live' : 'Connecting…'}
          </span>
        )}
      </div>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      <div className="mt-6">
        {tickets === null ? (
          <Skeleton className="h-56 w-full" />
        ) : !activeTicket || !detail ? (
          <EmptyState
            title="No active ticket"
            body="You don't have a ticket in progress right now."
            action={
              <Link to="/services">
                <Button size="sm">Browse services</Button>
              </Link>
            }
          />
        ) : (
          <div className="rounded-2xl border border-ink-100 bg-white p-8">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-400">Your ticket</p>
                <p className="token-display mt-1 text-6xl font-bold text-ink-900">{activeTicket.token_label}</p>
              </div>
              <TicketStatusBadge status={activeTicket.status} />
            </div>

            {detail.smart_alert && (
              <div className="mt-5 rounded-lg bg-amber-100 px-4 py-3 text-sm font-medium text-amber-600">
                Your turn is approaching. Please be ready.
              </div>
            )}
            {activeTicket.status === 'CALLED' && (
              <div className="mt-5 rounded-lg bg-signal-100 px-4 py-3 text-sm font-medium text-signal-700">
                You're being called! Please proceed to the counter.
              </div>
            )}

            <div className="mt-6 grid grid-cols-3 gap-4 border-t border-ink-100 pt-6 text-sm">
              <div>
                <p className="text-ink-400">Current token</p>
                <p className="mt-1 text-lg font-semibold text-ink-900">{detail.current_serving_label ?? '—'}</p>
              </div>
              <div>
                <p className="text-ink-400">People ahead</p>
                <p className="mt-1 text-lg font-semibold text-ink-900">{detail.people_ahead}</p>
              </div>
              <div>
                <p className="text-ink-400">Estimated wait</p>
                <p className="mt-1 text-lg font-semibold text-signal-700">~{detail.estimated_wait_minutes} min</p>
              </div>
            </div>

            {activeTicket.status === 'WAITING' && (
              <Button variant="secondary" size="sm" className="mt-6" onClick={() => setConfirmCancel(true)}>
                Cancel ticket
              </Button>
            )}
          </div>
        )}
      </div>

      {pastTickets.length > 0 && (
        <div className="mt-8">
          <p className="text-sm font-semibold text-ink-900">Recent activity</p>
          <ul className="mt-3 flex flex-col gap-2">
            {pastTickets.slice(0, 5).map((t) => (
              <li key={t.id} className="flex items-center justify-between rounded-lg border border-ink-100 bg-white px-4 py-3 text-sm">
                <span className="font-medium text-ink-800">{t.token_label}</span>
                <span className="text-ink-400">{new Date(t.created_at).toLocaleDateString()}</span>
                <TicketStatusBadge status={t.status} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <ConfirmDialog
        open={confirmCancel}
        title="Cancel this ticket?"
        body="You'll lose your place in the queue and will need to join again."
        confirmLabel="Cancel ticket"
        danger
        onConfirm={handleCancel}
        onCancel={() => setConfirmCancel(false)}
      />
    </AppShell>
  )
}
