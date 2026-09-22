import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { ErrorState, Skeleton } from '../../components/States'
import { QueueStatusBadge } from '../../components/Badge'
import type { Queue, Analytics } from '../../types'

export default function StaffDashboard() {
  const [queues, setQueues] = useState<Queue[] | null>(null)
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [queuesRes, analyticsRes] = await Promise.all([
          api.get<Queue[]>('/api/queues'),
          api.get<Analytics>('/api/analytics'),
        ])
        setQueues(queuesRes.data)
        setAnalytics(analyticsRes.data)
      } catch (err) {
        setError(extractErrorMessage(err))
      }
    }
    load()
  }, [])

  const openQueues = queues?.filter((q) => q.status === 'OPEN') ?? []

  return (
    <AppShell variant="staff">
      <h1 className="text-xl font-semibold text-ink-900">Operations overview</h1>
      <p className="mt-1 text-sm text-ink-500">A snapshot of everything running right now.</p>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Active queues" value={analytics?.active_queues} loading={!analytics} />
        <StatCard label="Served today" value={analytics?.customers_served_today} loading={!analytics} />
        <StatCard label="Avg. wait (min)" value={analytics?.average_wait_minutes} loading={!analytics} />
      </div>

      <div className="mt-8">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-ink-900">Open queues</p>
          <Link to="/staff/queues" className="text-sm font-medium text-signal-700 hover:underline">Manage queues →</Link>
        </div>

        <div className="mt-4 flex flex-col gap-2">
          {queues === null ? (
            <Skeleton className="h-16 w-full" />
          ) : openQueues.length === 0 ? (
            <p className="text-sm text-ink-400">No open queues right now.</p>
          ) : (
            openQueues.map((q) => (
              <Link
                key={q.id}
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
            ))
          )}
        </div>
      </div>
    </AppShell>
  )
}

function StatCard({ label, value, loading }: { label: string; value: number | undefined; loading: boolean }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-16" />
      ) : (
        <p className="mt-1 text-3xl font-semibold text-ink-900">{value}</p>
      )}
    </div>
  )
}
