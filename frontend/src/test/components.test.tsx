import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const apiMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));
vi.mock("../lib/api", async (orig) => {
  const actual = await orig<typeof import("../lib/api")>();
  return { ...actual, api: apiMock };
});

import { AuthProvider } from "../lib/auth";
import { ToastProvider } from "../components/Toast";
import Register from "../pages/auth/Register";
import { TokenStub } from "../components/TokenStub";
import { Wayzen } from "../components/Wayzen";
import type { Booking } from "../types";

const user = { id: "u1", email: "asha@example.com", full_name: "Asha Rao", role: "CUSTOMER", is_active: true,
  pref_sound_enabled: false, pref_browser_enabled: false, created_at: "2026-10-01T00:00:00Z" };

function shell(ui: React.ReactNode, path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider><AuthProvider>
        <Routes><Route path="*" element={ui} /><Route path="/dashboard" element={<p>dashboard page</p>} /></Routes>
      </AuthProvider></ToastProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => { apiMock.get.mockReset(); apiMock.post.mockReset(); apiMock.patch.mockReset(); });

describe("Register page", () => {
  beforeEach(() => { apiMock.get.mockRejectedValue({ isAxiosError: true, response: { status: 401 } }); });

  it("shows field errors and does not submit invalid input", async () => {
    shell(<Register />, "/register");
    await userEvent.click(await screen.findByRole("button", { name: "Create account" }));
    expect(screen.getByText("Enter your name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it("submits name, email, password and confirmation, then routes home", async () => {
    apiMock.post.mockResolvedValue({ data: { user, csrf_token: "c" } });
    shell(<Register />, "/register");
    await userEvent.type(await screen.findByLabelText("Full name"), "Asha Rao");
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Walkthrough2026");
    await userEvent.type(screen.getByLabelText("Confirm password"), "Walkthrough2026");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith("/api/auth/register", {
      full_name: "Asha Rao", email: "new@example.com", password: "Walkthrough2026", confirm_password: "Walkthrough2026" }));
    expect(await screen.findByText("dashboard page")).toBeInTheDocument();
  });

  it("maps server validation errors onto fields", async () => {
    apiMock.post.mockRejectedValue({ isAxiosError: true, response: { status: 409, data: { detail: "An account with this email already exists. Try signing in." } } });
    shell(<Register />, "/register");
    await userEvent.type(await screen.findByLabelText("Full name"), "Asha");
    await userEvent.type(screen.getByLabelText("Email"), "taken@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Walkthrough2026");
    await userEvent.type(screen.getByLabelText("Confirm password"), "Walkthrough2026");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
  });
});

const booking: Booking = {
  id: "b1", reference: "QF-H-ABCDEFG", status: "CONFIRMED", venue_id: "v", venue_name: "Greenleaf", venue_kind: "HOSPITAL",
  venue_timezone: "Asia/Kolkata", offering_id: "o", offering_name: "Cardiology consultation", specialization: "Cardiology",
  provider_id: "p", provider_name: "Dr. Vikram Shetty", start_at: "2026-10-30T04:10:00Z", end_at: "2026-10-30T04:30:00Z",
  service_date: "2026-10-30", token_label: "CAR1-004", notes: null, can_cancel: true, cancel_cutoff_minutes: 120,
  created_at: "2026-10-28T00:00:00Z", live: null,
};

describe("TokenStub", () => {
  it("shows token and venue-local time", () => {
    render(<TokenStub booking={booking} />);
    expect(screen.getByText("CAR1-004")).toBeInTheDocument();
    expect(screen.getByText(/9:40/)).toBeInTheDocument(); // 04:10Z is 09:40 in Asia/Kolkata
    expect(screen.getByText(/on the day of your visit/)).toBeInTheDocument();
  });
  it("shows live position and the serving token on the day", () => {
    render(<TokenStub booking={{ ...booking, live: { queue_status: "OPEN", current_token: "CAR1-002", delay_minutes: 10,
      position: 2, eta_minutes: 25, expected_start: null } }} />);
    expect(screen.getByText("CAR1-002")).toBeInTheDocument();
    expect(screen.getByText(/1 ahead of you, about 25 min to go/)).toBeInTheDocument();
    expect(screen.getByText(/10 min late/)).toBeInTheDocument();
  });
  it("announces the customer's turn", () => {
    render(<TokenStub booking={{ ...booking, status: "IN_SERVICE", live: { queue_status: "OPEN", current_token: "CAR1-004",
      delay_minutes: 0, position: 0, eta_minutes: 0, expected_start: null } }} />);
    expect(screen.getByText(/It's your turn/)).toBeInTheDocument();
  });
});

describe("Wayzen", () => {
  const action = { id: "a1", type: "book_appointment", status: "pending", expires_at: "2026-10-28T12:00:00Z", result: null,
    summary: { title: "Confirm appointment", venue: "Greenleaf", service: "Cardiology consultation", when: "Fri 30 Oct, 9:40 AM" } };

  beforeEach(() => {
    apiMock.get.mockImplementation((url: string) => url === "/api/auth/session"
      ? Promise.resolve({ data: { user, csrf_token: "c" } })
      : Promise.resolve({ data: { mode: "limited", welcome: "Hi! I'm Wayzen", suggested_questions: ["How do I cancel an appointment?"] } }));
  });

  it("shows limited mode, sources, and only books after Confirm", async () => {
    apiMock.post.mockImplementation((url: string) => {
      if (url === "/api/wayzen/chat") return Promise.resolve({ data: { session_id: "s1", message: {
        id: "m1", role: "assistant", content: "Here is a summary to confirm.", mode: "generated", created_at: "",
        sources: [{ id: "S1", title: "Cancellation and rescheduling policies", section: "", source: "guide:x", category: "policy", entity_id: null, score: 0.5, excerpt: "You can cancel…" }],
        actions: [action] } } });
      if (url === "/api/wayzen/actions/a1/confirm") return Promise.resolve({ data: { status: "executed", result: { reference: "QF-H-ZZZZZZZ" } } });
      return Promise.reject(new Error(url));
    });
    shell(<Wayzen />);
    await userEvent.click(await screen.findByRole("button", { name: "Open Wayzen assistant" }));
    expect(await screen.findByText(/Limited mode/)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "How do I cancel an appointment?" }));
    expect(await screen.findByText("Confirm appointment")).toBeInTheDocument();
    expect(screen.getByText(/Cancellation and rescheduling policies/)).toBeInTheDocument();
    expect(apiMock.post).not.toHaveBeenCalledWith("/api/wayzen/actions/a1/confirm");
    await userEvent.click(screen.getByRole("button", { name: "Confirm booking" }));
    expect(await screen.findByText(/View QF-H-ZZZZZZZ/)).toBeInTheDocument();
    expect(apiMock.post).toHaveBeenCalledWith("/api/wayzen/actions/a1/confirm");
  });

  it("keeps the draft and shows the error when sending fails", async () => {
    apiMock.post.mockRejectedValue({ isAxiosError: true, response: { status: 429, data: { detail: "Too many requests. Please wait a moment and try again." } } });
    shell(<Wayzen />);
    await userEvent.click(await screen.findByRole("button", { name: "Open Wayzen assistant" }));
    await userEvent.type(await screen.findByLabelText("Message Wayzen"), "hello{Enter}");
    expect(await screen.findByText(/Too many requests/)).toBeInTheDocument();
    expect(screen.getByLabelText("Message Wayzen")).toHaveValue("hello");
  });
});
