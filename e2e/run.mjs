// End-to-end browser walkthrough against a running QueueFlow (default http://localhost:8080).
// Usage: node e2e/run.mjs [baseUrl]   (needs the `playwright` package and a Chromium build)
// Optional: SHOTS=/path/to/dir to save screenshots; ADMIN_EMAIL / ADMIN_PASSWORD for the staff step.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const BASE = (process.argv[2] || "http://localhost:8080").replace(/\/$/, "");
const SHOTS = process.env.SHOTS;
const results = [];
const step = async (name, fn) => {
  try { await fn(); results.push(["PASS", name]); console.log("PASS", name); }
  catch (e) { results.push(["FAIL", name]); console.log("FAIL", name, "-", e.message.split("\n")[0]); throw e; }
};
const shot = async (page, name) => SHOTS && page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
const expectText = async (page, text, timeout = 8000) => page.getByText(text, { exact: false }).first().waitFor({ timeout });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
const page = await context.newPage();
const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(String(e)));
const email = `e2e${Date.now()}@example.com`;
const password = "Walkthrough2026";
let reference = "", token = "";

try {
  await step("landing renders", async () => { await page.goto(BASE); await expectText(page, "Know exactly when it's your turn"); await shot(page, "01-landing"); });
  await step("register validates and creates account", async () => {
    await page.goto(`${BASE}/register`);
    await page.getByRole("button", { name: "Create account" }).click();
    await expectText(page, "Enter your name");
    await page.getByLabel("Full name").fill("E2E Patient");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill("short");
    await page.getByLabel("Confirm password").fill("different");
    await page.getByRole("button", { name: "Create account" }).click();
    await expectText(page, "Use at least 10 characters");
    await expectText(page, "Passwords don't match");
    await shot(page, "02-register-errors");
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/dashboard");
    await expectText(page, "Hello, E2E");
  });
  await step("session cookie is HttpOnly and nothing in localStorage", async () => {
    const cookies = await context.cookies();
    const session = cookies.find((c) => c.name === "qf_session");
    if (!session?.httpOnly) throw new Error("session cookie missing or not HttpOnly");
    const stored = await page.evaluate(() => Object.keys(localStorage).join(","));
    if (stored.includes("token")) throw new Error("token in localStorage: " + stored);
  });
  await step("find hospital by specialization", async () => {
    await page.goto(`${BASE}/hospitals`);
    await page.getByRole("button", { name: "Cardiology" }).click();
    await expectText(page, "Greenleaf Multispeciality Hospital");
    await shot(page, "03-hospitals");
    await page.getByRole("link", { name: /Greenleaf Multispeciality Hospital/ }).click();
    await expectText(page, "Cardiology consultation");
    await shot(page, "04-hospital-detail");
  });
  await step("book cardiology slot and receive token", async () => {
    await page.getByRole("listitem").filter({ hasText: "Cardiology consultation" }).getByRole("link", { name: "Choose a time" }).click();
    await page.getByRole("button", { name: /Dr\. Vikram Shetty/ }).click();
    const days = page.getByRole("group", { name: "Choose a date" }).getByRole("button");
    for (let i = 1; i < 6; i++) {
      await days.nth(i).click();
      const slot = page.locator('button[aria-pressed]').filter({ hasText: /\d:\d\d/ }).first();
      if (await slot.isVisible({ timeout: 4000 }).catch(() => false)) { await slot.click(); break; }
    }
    await page.getByLabel("Note for the front desk (optional)").fill("E2E booking");
    await shot(page, "05-booking-review");
    await page.getByRole("button", { name: "Confirm booking" }).click();
    await page.waitForURL(/\/bookings\/QF-H-/);
    await expectText(page, "You're booked");
    token = (await page.locator(".token-display").first().innerText()).trim();
    reference = page.url().split("/bookings/")[1].split("?")[0];
    if (!/^CAR1-\d{3}$/.test(token)) throw new Error("unexpected token " + token);
    await shot(page, "06-booking-confirmed");
  });
  await step("booking visible in dashboard and list", async () => {
    await page.goto(`${BASE}/dashboard`);
    await expectText(page, token);
    await page.goto(`${BASE}/bookings`);
    await expectText(page, reference);
    await shot(page, "07-my-bookings");
  });
  await step("notification received", async () => {
    await page.getByRole("button", { name: /Notifications/ }).click();
    await expectText(page, `Token ${token}`);
    await page.keyboard.press("Escape");
  });
  await step("book shop service", async () => {
    await page.goto(`${BASE}/shops`);
    await page.getByRole("link", { name: /Bloom Unisex Salon/ }).click();
    await page.getByRole("listitem").filter({ hasText: "Haircut" }).getByRole("link", { name: "Choose a time" }).click();
    const days = page.getByRole("group", { name: "Choose a date" }).getByRole("button");
    for (let i = 1; i < 6; i++) {
      await days.nth(i).click();
      // Last slot of the day, so it can't overlap the cardiology visit booked earlier (overlaps are rejected).
      const slot = page.locator('button[aria-pressed]').filter({ hasText: /\d:\d\d/ }).last();
      if (await slot.isVisible({ timeout: 4000 }).catch(() => false)) { await slot.click(); break; }
    }
    await page.getByRole("button", { name: "Confirm booking" }).click();
    await page.waitForURL(/\/bookings\/QF-S-/);
    const shopToken = (await page.locator(".token-display").first().innerText()).trim();
    if (!/^(AS|RV)-\d{3}$/.test(shopToken)) throw new Error("unexpected shop token " + shopToken);
  });
  await step("reserve hotel room with server price", async () => {
    await page.goto(`${BASE}/hotels`);
    await page.getByRole("link", { name: /Palm Courtyard Hotel/ }).click();
    await expectText(page, "Standard Queen");
    const ist = (days) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date(Date.now() + days * 864e5));
    await page.getByLabel("Check-in").fill(ist(5));
    await page.getByLabel("Check-out").fill(ist(7));
    await page.getByRole("button", { name: "Check availability" }).click();
    await page.waitForTimeout(800);
    await shot(page, "08-hotel");
    await page.getByRole("listitem").filter({ hasText: "Standard Queen" }).getByRole("button", { name: "Reserve" }).click();
    await expectText(page, "Review your reservation");
    await shot(page, "09-hotel-review");
    await page.getByRole("button", { name: "Confirm reservation" }).click();
    await page.waitForURL(/\/reservations\/QF-R-/);
    await expectText(page, "Your room is reserved");
    await expectText(page, "7,168");
    await shot(page, "10-reservation");
  });
  await step("cancel hotel reservation within free window", async () => {
    await page.getByRole("button", { name: "Cancel reservation" }).click();
    await expectText(page, "no charge applies");
    await page.getByRole("dialog").getByRole("button", { name: "Cancel reservation" }).click();
    await expectText(page, "Cancelled");
  });
  await step("reschedule then cancel appointment", async () => {
    await page.goto(`${BASE}/bookings/${reference}`);
    await page.getByRole("button", { name: "Reschedule" }).click();
    const times = page.getByRole("dialog").getByRole("button").filter({ hasText: /\d:\d\d/ });
    await times.nth(2).click();
    await expectText(page, "Appointment rescheduled");
    await page.getByRole("button", { name: "Cancel booking" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel booking" }).click();
    await expectText(page, "Booking cancelled");
  });
  await step("other users' bookings are not accessible", async () => {
    const other = await browser.newContext();
    const p2 = await other.newPage();
    await p2.goto(`${BASE}/register`);
    await p2.getByLabel("Full name").fill("Other Person");
    await p2.getByLabel("Email").fill(`other${Date.now()}@example.com`);
    await p2.getByLabel("Password", { exact: true }).fill(password);
    await p2.getByLabel("Confirm password").fill(password);
    await p2.getByRole("button", { name: "Create account" }).click();
    await p2.waitForURL("**/dashboard");
    await p2.goto(`${BASE}/bookings/${reference}`);
    await expectText(p2, "Booking not found");
    await other.close();
  });
  await step("Wayzen answers with sources (limited mode if no provider)", async () => {
    await page.getByRole("button", { name: "Open Wayzen assistant" }).click();
    await page.getByRole("button", { name: "How do I cancel an appointment?" }).click();
    await page.waitForTimeout(3000);
    await shot(page, "11-wayzen");
    await expectText(page, "Cancellation and rescheduling policies", 15000);
    await page.getByRole("button", { name: "Close Wayzen" }).click();
  });
  if (process.env.ADMIN_EMAIL) {
    await step("staff runs the queue", async () => {
      const staff = await browser.newContext({ viewport: { width: 1280, height: 860 } });
      const sp = await staff.newPage();
      await sp.goto(`${BASE}/login`);
      await sp.getByLabel("Email").fill(process.env.ADMIN_EMAIL);
      await sp.getByLabel("Password").fill(process.env.ADMIN_PASSWORD);
      await sp.getByRole("button", { name: "Sign in" }).click();
      await sp.waitForURL("**/admin/venues");
      await shot(sp, "12-admin-venues");
      await sp.goto(`${BASE}/staff/venues`);
      await sp.getByRole("link", { name: /Greenleaf/ }).click();
      await expectText(sp, "Dr. Vikram Shetty");
      await shot(sp, "13-staff-board");
      await staff.close();
    });
  }
  await step("mobile layout has no horizontal scroll", async () => {
    const mobile = await browser.newContext({ viewport: { width: 375, height: 800 } });
    const mp = await mobile.newPage();
    for (const path of ["/", "/hospitals", "/login"]) {
      await mp.goto(BASE + path);
      const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 1) throw new Error(`${path} overflows by ${overflow}px`);
    }
    await shot(mp, "14-mobile");
    await mobile.close();
  });
  await step("no uncaught page errors", async () => { if (consoleErrors.length) throw new Error(consoleErrors.join("; ")); });
} catch {
  process.exitCode = 1;
} finally {
  await browser.close();
  console.log(`\n${results.filter((r) => r[0] === "PASS").length}/${results.length} steps passed`);
}
