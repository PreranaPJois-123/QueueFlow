import { useEffect, useState } from 'react'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import type { Service } from '../../types'

export default function StaffSettings() {
  const [services, setServices] = useState<Service[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { push } = useToast()

  async function load() {
    try {
      const { data } = await api.get<Service[]>('/api/services', { params: { active_only: false } })
      setServices(data)
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
      await api.post('/api/services', { name, description: description || undefined })
      push('Service created', 'success')
      setName('')
      setDescription('')
      setShowForm(false)
      load()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function toggleActive(service: Service) {
    try {
      await api.patch(`/api/services/${service.id}`, { is_active: !service.is_active })
      push(service.is_active ? 'Service deactivated' : 'Service activated', 'success')
      load()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    }
  }

  return (
    <AppShell variant="staff">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Settings</h1>
          <p className="mt-1 text-sm text-ink-500">Manage the services customers can join a queue for.</p>
        </div>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Close' : 'New service'}
        </Button>
      </div>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      {showForm && (
        <form onSubmit={handleCreate} className="mt-6 flex flex-col gap-4 rounded-2xl border border-ink-100 bg-white p-6 sm:max-w-md">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-700">Service name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. General Consultation"
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-700">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <Button type="submit" loading={submitting} className="w-full">Create service</Button>
        </form>
      )}

      <div className="mt-6">
        {services === null ? (
          <Skeleton className="h-40 w-full" />
        ) : services.length === 0 ? (
          <EmptyState title="No services yet" body="Create your first service above." />
        ) : (
          <ul className="flex flex-col gap-2">
            {services.map((s) => (
              <li key={s.id} className="flex items-center justify-between rounded-lg border border-ink-100 bg-white px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-ink-800">{s.name}</p>
                  {s.description && <p className="text-sm text-ink-400">{s.description}</p>}
                </div>
                <Button variant="secondary" size="sm" onClick={() => toggleActive(s)}>
                  {s.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
