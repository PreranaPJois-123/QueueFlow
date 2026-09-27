import { useEffect, useState } from 'react'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { Button } from '../../components/Button'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { useToast } from '../../components/Toast'
import type { Appointment } from '../../types'

interface StaffAppointment extends Appointment {
  customer_name: string
  service_name: string
}

export default function StaffAppointments() {
  const [appointments, setAppointments] = useState<StaffAppointment[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const { push } = useToast()

  async function load() {
    try {
      const { data } = await api.get<StaffAppointment[]>('/api/staff/appointments')
      setAppointments(data)
      setError(null)
    } catch (err) {
      setError(extractErrorMessage(err))
      setAppointments([])
    }
  }

  useEffect(() => {
    api.get<StaffAppointment[]>('/api/staff/appointments')
      .then(({ data }) => { setAppointments(data); setError(null) })
      .catch((err) => { setError(extractErrorMessage(err)); setAppointments([]) })
  }, [])

  async function act(appointment: StaffAppointment, action: 'check-in' | 'complete' | 'no-show') {
    setPendingId(appointment.id)
    try {
      await api.post(`/api/staff/appointments/${appointment.id}/${action}`)
      push('Appointment updated', 'success')
      await load()
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    } finally {
      setPendingId(null)
    }
  }

  return <AppShell variant="staff">
    <h1 className="text-xl font-semibold text-ink-900">Appointments</h1>
    <p className="mt-1 text-sm text-ink-500">Customer bookings and visit status across services.</p>
    {error && <div className="mt-6"><ErrorState message={error} /></div>}
    <div className="mt-6">
      {appointments === null ? <Skeleton className="h-40 w-full" /> : appointments.length === 0 && !error ? (
        <EmptyState title="No appointments yet" body="Bookings will appear here when customers schedule a service." />
      ) : <ul className="space-y-3">{appointments.map((appointment) => <li key={appointment.id} className="rounded-xl border border-ink-100 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-medium text-ink-900">{appointment.customer_name}</p>
            <p className="mt-1 text-sm text-ink-600">{appointment.service_name} · {new Date(appointment.scheduled_time).toLocaleString()}</p>
            {appointment.notes && <p className="mt-2 text-sm text-ink-500">{appointment.notes}</p>}
          </div>
          <span className="rounded-md bg-ink-50 px-2 py-1 text-xs font-medium text-ink-600">{appointment.status.replaceAll('_', ' ').toLowerCase()}</span>
        </div>
        {appointment.status === 'SCHEDULED' && <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" loading={pendingId === appointment.id} onClick={() => act(appointment, 'check-in')}>Check in</Button>
          <Button size="sm" variant="secondary" disabled={pendingId === appointment.id} onClick={() => act(appointment, 'no-show')}>No show</Button>
        </div>}
        {appointment.status === 'CHECKED_IN' && <Button size="sm" className="mt-4" loading={pendingId === appointment.id} onClick={() => act(appointment, 'complete')}>Complete visit</Button>}
      </li>)}</ul>}
    </div>
  </AppShell>
}
