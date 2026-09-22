export type UserRole = 'CUSTOMER' | 'STAFF' | 'ADMIN'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export type QueueStatus = 'OPEN' | 'PAUSED' | 'CLOSED'
export type TicketStatus = 'WAITING' | 'CALLED' | 'SERVING' | 'SERVED' | 'SKIPPED' | 'CANCELLED'
export type AppointmentStatus = 'SCHEDULED' | 'CHECKED_IN' | 'COMPLETED' | 'CANCELLED' | 'NO_SHOW'

export interface Service {
  id: string
  name: string
  description: string | null
  is_active: boolean
  created_at: string
}

export interface Queue {
  id: string
  service_id: string
  name: string
  status: QueueStatus
  current_serving_number: number | null
  created_at: string
}

export interface Ticket {
  id: string
  queue_id: string
  customer_id: string
  token_number: number
  token_label: string
  status: TicketStatus
  created_at: string
  called_at: string | null
  serving_started_at: string | null
  served_at: string | null
}

export interface TicketDetail {
  ticket: Ticket
  people_ahead: number
  estimated_wait_minutes: number
  current_serving_label: string | null
  queue_status: QueueStatus
  smart_alert: boolean
}

export interface QueueState {
  queue_id: string
  queue_name: string
  status: QueueStatus
  current_serving_label: string | null
  now_serving_ticket_id: string | null
  next_ticket_label: string | null
  waiting_labels: string[]
  waiting_count: number
}

export interface Appointment {
  id: string
  service_id: string
  scheduled_time: string
  status: AppointmentStatus
  notes: string | null
  created_at: string
}

export interface Analytics {
  customers_served_today: number
  average_wait_minutes: number
  average_service_minutes: number
  active_queues: number
  completed_tickets_today: number
  skipped_tickets_today: number
  busiest_hour: number | null
}
