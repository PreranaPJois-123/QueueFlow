import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { QueueStatusBadge } from '../../components/Badge'
import { useToast } from '../../components/Toast'
import { useQueueSocket } from '../../lib/useQueueSocket'
import type { Queue, QueueState, Ticket } from '../../types'

type ActionKey = 'next' | 'serve' | 'skip' | 'pause' | 'resume' | 'close' | null

export default function StaffQueueDetail() {
  const { id } = useParams<{ id: string }>()
  const [queue, setQueue] = useState<Queue | null>(null)
  const [state, setState] = useState<QueueState | null>(null)
  const [calledTicket, setCalledTicket] = useState<Ticket | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<ActionKey>(null)
  const { push } = useToast()
  const { state: liveState, connected } = useQueueSocket(id ?? null)

  async function loadQueue() {
    if (!id) return
    try {
      const { data } = await api.get<Queue>(`/api/queues/${id}`)
      setQueue(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function loadState() {
    if (!id) return
    try {
      const { data } = await api.get<QueueState>(`/api/staff/queues/${id}/state`)
      setState(data)
      await loadCalledTicket(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function loadCalledTicket(stateData: QueueState | null) {
    if (!stateData?.now_serving_ticket_id) {
      setCalledTicket(null)
      return
    }
    try {
      const { data } = await api.get<{ ticket: Ticket }>(`/api/tickets/${stateData.now_serving_ticket_id}`)
      setCalledTicket(data.ticket)
    } catch {
      setCalledTicket(null)
    }
  }

  useEffect(() => {
    loadQueue()
    loadState()
  }, [id])

  useEffect(() => {
    if (liveState) {
      setState(liveState)
      setQueue((prev) => (prev ? { ...prev, status: liveState.status } : prev))
      loadCalledTicket(liveState)
    }
  }, [liveState])

  async function runAction(key: ActionKey, fn: () => Promise<unknown>, successMsg: string) {
    setPending(key)
    try {
      await fn()
      push(successMsg, 'success')
      await loadQueue()
      await loadState()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    } finally {
      setPending(null)
    }
  }

  if (!queue || !state) {
    return (
      <AppShell variant="staff">
        {error ? <ErrorState message={error} /> : <Skeleton className="h-80 w-full" />}
      </AppShell>
    )
  }

  const hasCalledTicket = Boolean(state.now_serving_ticket_id)

  return (
    <AppShell variant="staff">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">{queue.name}</h1>
          <div className="mt-1 flex items-center gap-2">
            <QueueStatusBadge status={queue.status} />
            <span className={`text-xs font-medium ${connected ? 'text-signal-600' : 'text-ink-400'}`}>
              {connected ? '● Live' : 'Connecting…'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {queue.status === 'OPEN' && (
            <Button variant="secondary" size="sm" loading={pending === 'pause'}
              onClick={() => runAction('pause', () => api.post(`/api/staff/queues/${id}/pause`), 'Queue paused')}>
              Pause queue
            </Button>
          )}
          {queue.status === 'PAUSED' && (
            <Button variant="secondary" size="sm" loading={pending === 'resume'}
              onClick={() => runAction('resume', () => api.post(`/api/staff/queues/${id}/resume`), 'Queue resumed')}>
              Resume queue
            </Button>
          )}
          {queue.status !== 'CLOSED' && (
            <Button variant="danger" size="sm" loading={pending === 'close'}
              onClick={() => runAction('close', () => api.post(`/api/staff/queues/${id}/close`), 'Queue closed')}>
              Close queue
            </Button>
          )}
        </div>
      </div>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 lg:col-span-2">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-400">Now serving</p>
          <p className="token-display mt-1 text-5xl font-bold text-ink-900">
            {state.current_serving_label ?? '—'}
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              disabled={queue.status !== 'OPEN' || hasCalledTicket}
              loading={pending === 'next'}
              onClick={() => runAction('next', () => api.post(`/api/staff/queues/${id}/next`), 'Called next customer')}
            >
              Call next
            </Button>
            {hasCalledTicket && calledTicket && (
              <>
                <Button
                  variant="secondary"
                  loading={pending === 'serve'}
                  onClick={() => runAction('serve', () => api.post(`/api/staff/tickets/${calledTicket.id}/serve`), 'Marked as served')}
                >
                  Mark served
                </Button>
                <Button
                  variant="danger"
                  loading={pending === 'skip'}
                  onClick={() => runAction('skip', () => api.post(`/api/staff/tickets/${calledTicket.id}/skip`), 'Ticket skipped')}
                >
                  Skip
                </Button>
              </>
            )}
          </div>
          {queue.status !== 'OPEN' && (
            <p className="mt-3 text-xs text-ink-400">
              Resume the queue to call the next customer.
            </p>
          )}
          {hasCalledTicket && (
            <p className="mt-3 text-xs text-ink-400">
              Serve or skip {calledTicket?.token_label ?? 'the current ticket'} before calling the next one.
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-ink-100 bg-white p-6">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-400">Next</p>
          <p className="token-display mt-1 text-3xl font-semibold text-ink-800">
            {state.next_ticket_label ?? '—'}
          </p>
          <p className="mt-4 text-xs font-medium uppercase tracking-wide text-ink-400">Waiting ({state.waiting_count})</p>
          {state.waiting_labels.length === 0 ? (
            <p className="mt-2 text-sm text-ink-400">No one waiting.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-2">
              {state.waiting_labels.map((label) => (
                <li key={label} className="rounded-md bg-ink-50 px-2.5 py-1 text-xs font-medium text-ink-600">
                  {label}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  )
}
