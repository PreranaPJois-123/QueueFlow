import type { VenueDetail, VenueKind } from "../types";

export interface VenueForm {
  kind: VenueKind; name: string; city: string; address: string; description: string; phone: string; category: string;
  timezone: string; currency: string; is_active: boolean; booking_horizon_days: number; min_notice_minutes: number;
  cancel_cutoff_minutes: number; tax_rate: string; check_in_time: string; check_out_time: string; free_cancellation_hours: number;
}

export const emptyVenue: VenueForm = {
  kind: "HOSPITAL", name: "", city: "", address: "", description: "", phone: "", category: "", timezone: "Asia/Kolkata",
  currency: "INR", is_active: true, booking_horizon_days: 30, min_notice_minutes: 30, cancel_cutoff_minutes: 120,
  tax_rate: "0", check_in_time: "14:00", check_out_time: "11:00", free_cancellation_hours: 24,
};

export function venueToForm(v: VenueDetail): VenueForm {
  return { ...emptyVenue, ...v, phone: v.phone ?? "", category: v.category ?? "", tax_rate: String(v.tax_rate),
    check_in_time: v.check_in_time?.slice(0, 5) ?? "14:00", check_out_time: v.check_out_time?.slice(0, 5) ?? "11:00" };
}

export function venuePayload(f: VenueForm) {
  const hotel = f.kind === "HOTEL";
  return { ...f, phone: f.phone || null, category: f.kind === "SHOP" ? f.category || null : null,
    tax_rate: hotel ? f.tax_rate : "0", check_in_time: hotel ? f.check_in_time : null, check_out_time: hotel ? f.check_out_time : null };
}

