import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, extractErrorMessage } from '../../lib/api'
import { AppShell } from '../../components/AppShell'
import { EmptyState, ErrorState, Skeleton } from '../../components/States'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import type { Service, Queue } from '../../types'

export default function Services() {
  const [services, setServices] = useState<Service[] | null>(null)
  const [queuesByService, setQueuesByService] = useState<Record<string, Queue[]>>({})
  const [error, setError] = useState<string | null>(null)
  const [joiningQueueId, setJoiningQueueId] = useState<string | null>(null)
  const { push } = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const { data } = await api.get<Service[]>('/api/services')
        setServices(data)
        const results = await Promise.all(
          data.map((s) => api.get<Queue[]>('/api/queues', { params: { service_id: s.id } }))
        )
        const map: Record<string, Queue[]> = {}
        data.forEach((s, i) => { map[s.id] = results[i].data })
        setQueuesByService(map)
      } catch (err) {
        setError(extractErrorMessage(err))
      }
    }
    load()
  }, [])

  async function handleJoin(queueId: string) {
    setJoiningQueueId(queueId)
    try {
      await api.post(`/api/queues/${queueId}/join`)
      push('You joined the queue!', 'success')
      navigate('/my-ticket')
    } catch (err) {
      push(extractErrorMessage(err), 'error')
    } finally {
      setJoiningQueueId(null)
    }
  }

  return (
    <AppShell variant="customer">
      <h1 className="text-xl font-semibold text-ink-900">Services</h1>
      <p className="mt-1 text-sm text-ink-500">Choose a service to see its open queues.</p>

      {error && <div className="mt-6"><ErrorState message={error} /></div>}

      <div className="mt-6 flex flex-col gap-6">
        {services === null ? (
          <>
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </>
        ) : services.length === 0 ? (
          <EmptyState title="No services available yet" body="Check back once staff have added services." />
        ) : (
          services.map((service) => {
            const queues = queuesByService[service.id] ?? []
            return (
              <div key={service.id} className="rounded-2xl border border-ink-100 bg-white p-5">
                <p className="text-sm font-semibold text-ink-900">{service.name}</p>
                {service.description && <p className="mt-1 text-sm text-ink-500">{service.description}</p>}

                {queues.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-400">No queues open for this service right now.</p>
                ) : (
                  <ul className="mt-4 flex flex-col gap-2">
                    {queues.map((q) => (
                      <li key={q.id} className="flex items-center justify-between rounded-lg border border-ink-100 px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-ink-800">{q.name}</p>
                          <p className="text-xs text-ink-400">{q.status === 'OPEN' ? 'Accepting customers' : q.status.toLowerCase()}</p>
                        </div>
                        <Button
                          size="sm"
                          disabled={q.status !== 'OPEN'}
                          loading={joiningQueueId === q.id}
                          onClick={() => handleJoin(q.id)}
                        >
                          Join queue
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )
          })
        )}
      </div>
    </AppShell>
  )
}
