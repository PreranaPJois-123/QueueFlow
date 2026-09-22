import { useEffect, useState } from 'react'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import type { Appointment, Service } from '../../types'

export default function Appointments() {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [serviceId, setServiceId] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { push } = useToast()

  async function load() {
    try {
      const [apptRes, svcRes] = await Promise.all([
        api.get<Appointment[]>('/api/appointments'),
        api.get<Service[]>('/api/services'),
      ])
      setAppointments(apptRes.data)
      setServices(svcRes.data)
      if (svcRes.data.length > 0) setServiceId(svcRes.data[0].id)
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
      await api.post('/api/appointments', {
        service_id: serviceId,
        scheduled_time: new Date(scheduledTime).toISOString(),
        notes: notes || undefined,
      })
      push('Appointment scheduled', 'success')
      setShowForm(false)
      setNotes('')
      load()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCancel(id: string) {
    try {
      await api.post(`/api/appointments/${id}/cancel`)
      push('Appointment cancelled', 'success')
      load()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    }
  }

  return (
    <AppShell variant="customer">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Appointments</h1>
          <p className="mt-1 text-sm text-ink-500">Schedule ahead instead of joining a live queue.</p>
        </div>
        {services.length > 0 && (
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Close' : 'New appointment'}
          </Button>
        )}
      </div>

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
            <label className="mb-1.5 block text-sm font-medium text-ink-700">Date &amp; time</label>
            <input
              type="datetime-local"
              required
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-700">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <Button type="submit" loading={submitting} className="w-full">Schedule</Button>
        </form>
      )}

      <div className="mt-6">
        {appointments === null ? (
          <Skeleton className="h-32 w-full" />
        ) : appointments.length === 0 ? (
          <EmptyState title="No appointments yet" body="Schedule one above once services are available." />
        ) : (
          <ul className="flex flex-col gap-2">
            {appointments.map((a) => (
              <li key={a.id} className="flex items-center justify-between rounded-lg border border-ink-100 bg-white px-4 py-3 text-sm">
                <div>
                  <p className="font-medium text-ink-800">{new Date(a.scheduled_time).toLocaleString()}</p>
                  {a.notes && <p className="text-ink-400">{a.notes}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-ink-500">{a.status.replace('_', ' ').toLowerCase()}</span>
                  {a.status === 'SCHEDULED' && (
                    <Button variant="ghost" size="sm" onClick={() => handleCancel(a.id)}>Cancel</Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
