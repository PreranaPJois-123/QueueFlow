import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { QueueStatusBadge } from '../../components/Badge'
import { useToast } from '../../components/Toast'
import type { Queue, Service } from '../../types'

export default function StaffQueues() {
  const [queues, setQueues] = useState<Queue[] | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [serviceId, setServiceId] = useState('')
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { push } = useToast()

  async function load() {
    try {
      const [queuesRes, servicesRes] = await Promise.all([
        api.get<Queue[]>('/api/queues'),
        api.get<Service[]>('/api/services'),
      ])
      setQueues(queuesRes.data)
      setServices(servicesRes.data)
      if (servicesRes.data.length > 0) setServiceId(servicesRes.data[0].id)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await api.post('/api/queues', { service_id: serviceId, name })
      push('Queue created', 'success')
      setName('')
      setShowForm(false)
      load()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AppShell variant="staff">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Queues</h1>
          <p className="mt-1 text-sm text-ink-500">Every queue across all services.</p>
        </div>
        {services.length > 0 && (
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Close' : 'New queue'}
          </Button>
        )}
      </div>

      {services.length === 0 && (
        <p className="mt-4 text-sm text-ink-400">
          Create a service in <Link to="/staff/settings" className="text-signal-700 hover:underline">Settings</Link> before opening a queue.
        </p>
      )}

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      {showForm && (
        <form onSubmit={handleCreate} className="mt-6 flex flex-col gap-4 rounded-2xl border border-ink-100 bg-white p-6 sm:max-w-md">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-700">Service</label>
            <select
              value={serviceId}
              onChange={(e) => setServiceId(e.target.value)}
              className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            >
              {services.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-700">Queue name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Main Counter"
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <Button type="submit" loading={submitting} className="w-full">Create queue</Button>
        </form>
      )}

      <div className="mt-6">
        {queues === null ? (
          <Skeleton className="h-40 w-full" />
        ) : queues.length === 0 ? (
          <EmptyState title="No queues yet" body="Create your first queue above." />
        ) : (
          <ul className="flex flex-col gap-2">
            {queues.map((q) => (
              <li key={q.id}>
                <Link
                  to={`/staff/queue/${q.id}`}
                  className="flex items-center justify-between rounded-lg border border-ink-100 bg-white px-4 py-3 hover:border-ink-200"
                >
                  <div>
                    <p className="text-sm font-medium text-ink-800">{q.name}</p>
                    <p className="text-xs text-ink-400">
                      Now serving {q.current_serving_number ? `#${q.current_serving_number}` : '—'}
                    </p>
                  </div>
                  <QueueStatusBadge status={q.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
