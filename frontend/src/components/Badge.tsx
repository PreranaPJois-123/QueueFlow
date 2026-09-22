import type { TicketStatus, QueueStatus } from '../types'

const ticketStyles: Record<TicketStatus, string> = {
  WAITING: 'bg-ink-100 text-ink-700',
  CALLED: 'bg-amber-100 text-amber-600',
  SERVING: 'bg-signal-100 text-signal-700',
  SERVED: 'bg-signal-50 text-signal-600',
  SKIPPED: 'bg-rose-100 text-rose-600',
  CANCELLED: 'bg-ink-50 text-ink-400',
}

const queueStyles: Record<QueueStatus, string> = {
  OPEN: 'bg-signal-100 text-signal-700',
  PAUSED: 'bg-amber-100 text-amber-600',
  CLOSED: 'bg-ink-100 text-ink-500',
}

export function TicketStatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${ticketStyles[status]}`}>
      {status.charAt(0) + status.slice(1).toLowerCase()}
    </span>
  )
}

export function QueueStatusBadge({ status }: { status: QueueStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${queueStyles[status]}`}>
      {status.charAt(0) + status.slice(1).toLowerCase()}
    </span>
  )
}
