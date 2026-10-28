import { describe, expect, it } from "vitest";
import { passwordProblem, validateRegister } from "../lib/validation/auth";
import { groupSlots, validateStay } from "../lib/booking";

describe("registration validation", () => {
  it("requires every field and a valid email", () => {
    const errors = validateRegister({ fullName: " ", email: "nope", password: "", confirmPassword: "" });
    expect(errors).toMatchObject({ fullName: "Enter your name", email: "Enter a valid email address",
      confirmPassword: "Re-enter your password" });
  });
  it("mirrors the server password policy", () => {
    expect(passwordProblem("short1")).toMatch(/10 characters/);
    expect(passwordProblem("onlyletterslong")).toMatch(/letter and one number/);
    expect(passwordProblem("priya2026xyz", "priya@example.com")).toMatch(/email name/);
    expect(passwordProblem("Walkthrough2026")).toBeNull();
  });
  it("detects mismatched confirmation", () => {
    const errors = validateRegister({ fullName: "A", email: "a@example.com", password: "Walkthrough2026", confirmPassword: "x" });
    expect(errors).toEqual({ confirmPassword: "Passwords don't match" });
  });
});

describe("stay validation", () => {
  const today = "2026-10-28";
  it("rejects past check-in, reversed and over-long stays", () => {
    expect(validateStay("2026-10-27", "2026-10-29", 2, today).checkIn).toBeTruthy();
    expect(validateStay("2026-10-30", "2026-10-30", 2, today).checkOut).toMatch(/after check-in/);
    expect(validateStay("2026-10-30", "2026-12-30", 2, today).checkOut).toMatch(/30 nights/);
    expect(validateStay("2026-10-30", "2026-11-01", 0, today).guests).toBeTruthy();
    expect(validateStay("2026-10-30", "2026-11-01", 2, today)).toEqual({});
  });
});

describe("slot grouping", () => {
  it("groups by venue-local hour, not browser time", () => {
    const slot = (iso: string) => ({ start_at: iso, end_at: iso, provider_id: "p", provider_name: "P" });
    // 03:30Z = 09:00 IST, 08:30Z = 14:00 IST, 12:00Z = 17:30 IST
    const groups = groupSlots([slot("2026-10-30T03:30:00Z"), slot("2026-10-30T08:30:00Z"), slot("2026-10-30T12:00:00Z")], "Asia/Kolkata");
    expect(groups.Morning).toHaveLength(1);
    expect(groups.Afternoon).toHaveLength(1);
    expect(groups.Evening).toHaveLength(1);
  });
});
