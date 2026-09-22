import { useEffect, useState } from 'react'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { ErrorState, Skeleton } from '../../components/States'
import type { Analytics } from '../../types'

export default function StaffAnalytics() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<Analytics>('/api/analytics')
      .then((r) => setData(r.data))
      .catch((err) => setError(extractErrorMessage(err)))
  }, [])

  return (
    <AppShell variant="staff">
      <h1 className="text-xl font-semibold text-ink-900">Analytics</h1>
      <p className="mt-1 text-sm text-ink-500">Real activity across every queue.</p>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      {!data ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <Stat label="Served today" value={data.customers_served_today} />
            <Stat label="Skipped today" value={data.skipped_tickets_today} />
            <Stat label="Active queues" value={data.active_queues} />
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Stat label="Average wait" value={`${data.average_wait_minutes} min`} />
            <Stat label="Average service time" value={`${data.average_service_minutes} min`} />
          </div>

          <div className="mt-8 rounded-2xl border border-ink-100 bg-white p-6">
            <p className="text-sm font-semibold text-ink-900">Busiest hour</p>
            {data.busiest_hour === null ? (
              <p className="mt-2 text-sm text-ink-400">Not enough activity yet to identify a busiest hour.</p>
            ) : (
              <p className="mt-2 text-sm text-ink-600">
                Most tickets have been created around{' '}
                <span className="font-medium text-ink-900">{formatHour(data.busiest_hour)}</span>.
              </p>
            )}
          </div>
        </>
      )}
    </AppShell>
  )
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink-900">{value}</p>
    </div>
  )
}

function formatHour(hour: number): string {
  const period = hour >= 12 ? 'PM' : 'AM'
  const displayHour = hour % 12 === 0 ? 12 : hour % 12
  return `${displayHour}:00 ${period}`
}
