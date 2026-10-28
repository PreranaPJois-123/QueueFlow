export type UserRole = "CUSTOMER" | "STAFF" | "ADMIN";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  pref_sound_enabled: boolean;
  pref_browser_enabled: boolean;
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

// ----------------------------- Venues & bookings -----------------------------

export type VenueKind = "HOSPITAL" | "SHOP" | "HOTEL";
export type BookingStatus = "CONFIRMED" | "CHECKED_IN" | "IN_SERVICE" | "COMPLETED" | "CANCELLED" | "NO_SHOW";
export type ReservationStatus = "CONFIRMED" | "CHECKED_IN" | "CHECKED_OUT" | "CANCELLED" | "NO_SHOW";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface VenueSummary {
  id: string;
  kind: VenueKind;
  name: string;
  slug: string;
  city: string;
  address: string;
  description: string;
  category: string | null;
  is_sample: boolean;
  is_active: boolean;
  currency: string;
  timezone: string;
  // Optional listing facts: shown only when the backend provides them.
  service_count?: number;
  provider_count?: number;
  starting_price?: string | null;
  highlights?: string[];
}

export interface Specialization {
  id: string;
  name: string;
  slug: string;
  description: string;
}

export interface Offering {
  id: string;
  name: string;
  description: string;
  duration_minutes: number;
  price: string | null;
  specialization_id: string | null;
  is_active: boolean;
}

export interface Provider {
  id: string;
  name: string;
  title: string;
  bio: string;
  specialization_id: string | null;
  is_active: boolean;
  offering_ids: string[];
}

export interface RoomType {
  id: string;
  name: string;
  description: string;
  amenities: string;
  max_occupancy: number;
  nightly_rate: string;
  total_rooms: number;
  is_active: boolean;
}

export interface VenueDetail extends VenueSummary {
  phone: string | null;
  booking_horizon_days: number;
  min_notice_minutes: number;
  cancel_cutoff_minutes: number;
  tax_rate: string;
  check_in_time: string | null;
  check_out_time: string | null;
  free_cancellation_hours: number;
  specializations: Specialization[];
  offerings: Offering[];
  providers: Provider[];
  room_types: RoomType[];
}

export interface Slot {
  start_at: string;
  end_at: string;
  provider_id: string;
  provider_name: string;
}

export interface Quote {
  room_type_id: string;
  room_type_name: string;
  check_in: string;
  check_out: string;
  guests: number;
  rooms: number;
  nights: number;
  nightly_rate: string;
  subtotal: string;
  tax_rate: string;
  taxes: string;
  total: string;
  currency: string;
  rooms_left: number;
  available: boolean;
  free_cancellation_until: string;
}

export interface LiveQueue {
  queue_status: "OPEN" | "PAUSED";
  current_token: string | null;
  delay_minutes: number;
  position: number | null;
  eta_minutes: number | null;
  expected_start: string | null;
}

export interface Booking {
  id: string;
  reference: string;
  status: BookingStatus;
  venue_id: string;
  venue_name: string;
  venue_kind: VenueKind;
  venue_timezone: string;
  offering_id: string;
  offering_name: string;
  specialization: string | null;
  provider_id: string;
  provider_name: string;
  start_at: string;
  end_at: string;
  service_date: string;
  token_label: string;
  notes: string | null;
  can_cancel: boolean;
  cancel_cutoff_minutes: number;
  created_at: string;
  live: LiveQueue | null;
}

export interface Reservation {
  id: string;
  reference: string;
  status: ReservationStatus;
  venue_id: string;
  venue_name: string;
  venue_timezone: string;
  room_type_id: string;
  room_type_name: string;
  check_in: string;
  check_out: string;
  check_in_time: string | null;
  check_out_time: string | null;
  guests: number;
  rooms: number;
  nights: number;
  nightly_rate: string;
  subtotal: string;
  taxes: string;
  total: string;
  currency: string;
  cancellation_fee: string;
  special_requests: string | null;
  free_cancellation_until: string;
  created_at: string;
}

export interface AppNotification {
  id: string;
  type: string;
  message: string;
  booking_id: string | null;
  reservation_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface WayzenSource {
  id: string;
  title: string;
  section: string;
  source: string;
  category: string;
  entity_id: string | null;
  score: number;
  excerpt: string;
}

export interface WayzenAction {
  id: string;
  type: "book_appointment" | "reserve_hotel" | "cancel_booking" | "cancel_reservation";
  status: "pending" | "executed" | "dismissed" | "expired" | "failed";
  summary: Record<string, string | number | boolean | null>;
  result: Record<string, string> | null;
  expires_at: string;
}

export interface WayzenMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode: "generated" | "limited" | "error" | null;
  sources: WayzenSource[];
  created_at: string;
  actions: WayzenAction[];
}
