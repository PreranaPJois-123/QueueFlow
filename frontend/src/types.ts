export type UserRole = "CUSTOMER" | "STAFF" | "ADMIN";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type QueueStatus = "OPEN" | "PAUSED" | "CLOSED";
export type TicketStatus =
  | "WAITING"
  | "CALLED"
  | "SERVING"
  | "SERVED"
  | "SKIPPED"
  | "CANCELLED";
export type AppointmentStatus =
  | "SCHEDULED"
  | "CHECKED_IN"
  | "COMPLETED"
  | "CANCELLED"
  | "NO_SHOW";

export interface Service {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Queue {
  id: string;
  service_id: string;
  name: string;
  status: QueueStatus;
  current_serving_number: number | null;
  created_at: string;
}

export interface Ticket {
  id: string;
  queue_id: string;
  customer_id: string;
  token_number: number;
  token_label: string;
  status: TicketStatus;
  created_at: string;
  called_at: string | null;
  serving_started_at: string | null;
  served_at: string | null;
}

export interface TicketDetail {
  queue_name: string;
  service_name: string;
  prediction_source: string;
  prediction_samples: number;
  estimated_service_minutes: number;
  ticket: Ticket;
  people_ahead: number;
  estimated_wait_minutes: number;
  current_serving_label: string | null;
  queue_status: QueueStatus;
  smart_alert: boolean;
}

export interface QueueState {
  queue_id: string;
  queue_name: string;
  status: QueueStatus;
  current_serving_label: string | null;
  now_serving_ticket_id: string | null;
  next_ticket_label: string | null;
  waiting_labels: string[];
  waiting_count: number;
}

export interface Appointment {
  id: string;
  service_id: string;
  scheduled_time: string;
  status: AppointmentStatus;
  notes: string | null;
  created_at: string;
}

export interface Analytics {
  customers_served_today: number;
  average_wait_minutes: number;
  average_service_minutes: number;
  active_queues: number;
  completed_tickets_today: number;
  skipped_tickets_today: number;
  busiest_hour: number | null;
}

export interface QueueSummary extends Queue, QueueState {
  service_name: string;
  service_active: boolean;
  estimated_wait_minutes: number;
  estimated_service_minutes: number;
  prediction_source: string;
  prediction_samples: number;
}
export interface NamedTicket extends Ticket {
  queue_name: string;
  service_name: string;
}
export interface NamedAppointment extends Appointment {
  service_name: string;
}
export interface Notification {
  id: string;
  message: string;
  is_read: boolean;
  created_at: string;
}
export interface CustomerData {
  tickets: NamedTicket[];
  appointments: NamedAppointment[];
  notifications: Notification[];
}
export interface CustomerRecord extends User {
  tickets: NamedTicket[];
  appointments: NamedAppointment[];
}
export interface OperatingTicket extends NamedTicket {
  customer_name: string;
  customer_email: string;
  waiting_minutes: number;
}
export interface Trends {
  daily: { date: string; tickets: number; served: number; skipped: number }[];
  total_tickets: number;
  total_served: number;
  completion_rate: number;
  skip_rate: number;
  waiting: number;
  serving: number;
  appointments: number;
  active_appointments: number;
}
