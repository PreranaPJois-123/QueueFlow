import { useEffect, useState } from 'react'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import type { Queue, Ticket } from '../../types'

interface Row extends Ticket {
  queueName: string
}

export default function StaffCustomers() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const { data: queues } = await api.get<Queue[]>('/api/queues')
        const results = await Promise.all(
          queues.map((q) => api.get<Ticket[]>(`/api/staff/queues/${q.id}/waiting`))
        )
        const combined: Row[] = []
        queues.forEach((q, i) => {
          results[i].data.forEach((t) => combined.push({ ...t, queueName: q.name }))
        })
        combined.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        setRows(combined)
      } catch (err) {
        setError(extractErrorMessage(err))
      }
    }
    load()
  }, [])

  return (
    <AppShell variant="staff">
      <h1 className="text-xl font-semibold text-ink-900">Waiting customers</h1>
      <p className="mt-1 text-sm text-ink-500">Everyone currently waiting, across every queue.</p>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      <div className="mt-6">
        {rows === null ? (
          <Skeleton className="h-64 w-full" />
        ) : rows.length === 0 ? (
          <EmptyState title="No one is waiting" body="All queues are currently empty." />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-ink-100 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-ink-100 bg-ink-50 text-xs font-medium uppercase tracking-wide text-ink-400">
                <tr>
                  <th className="px-4 py-3">Token</th>
                  <th className="px-4 py-3">Queue</th>
                  <th className="px-4 py-3">Joined</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-ink-50 last:border-0">
                    <td className="px-4 py-3 font-medium text-ink-800">{row.token_label}</td>
                    <td className="px-4 py-3 text-ink-600">{row.queueName}</td>
                    <td className="px-4 py-3 text-ink-400">{new Date(row.created_at).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  )
}
