import { addDays } from "./format";
import type { Slot } from "../types";

export function groupSlots(slots: Slot[], timeZone: string) {
  const hour = (iso: string) => Number(new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", hour12: false }).format(new Date(iso)));
  return {
    Morning: slots.filter((s) => hour(s.start_at) < 12),
    Afternoon: slots.filter((s) => hour(s.start_at) >= 12 && hour(s.start_at) < 17),
    Evening: slots.filter((s) => hour(s.start_at) >= 17),
  };
}

export function validateStay(checkIn: string, checkOut: string, guests: number, today: string) {
  const errors: { checkIn?: string; checkOut?: string; guests?: string } = {};
  if (!checkIn) errors.checkIn = "Choose a check-in date";
  else if (checkIn < today) errors.checkIn = "Check-in can't be in the past";
  if (!checkOut) errors.checkOut = "Choose a check-out date";
  else if (checkIn && checkOut <= checkIn) errors.checkOut = "Check-out must be after check-in";
  else if (checkIn && checkOut > addDays(checkIn, 30)) errors.checkOut = "Stays are limited to 30 nights";
  if (!Number.isInteger(guests) || guests < 1) errors.guests = "At least 1 guest";
  return errors;
}

