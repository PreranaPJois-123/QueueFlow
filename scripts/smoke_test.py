#!/usr/bin/env python3
"""End-to-end API smoke test against a running QueueFlow deployment (stdlib only).

Usage:
  python3 scripts/smoke_test.py http://HOST

Exercises: health, registration (cookie session + CSRF), role-escalation rejection,
hospital catalogue, slot lookup, booking with idempotency, isolation from another
user, hotel quote + reservation + cancellation, Wayzen status/chat, logout revocation.
Requires sample venues (SEED_SAMPLE_DATA=true or `python -m app.seed`). It creates
uniquely named test accounts and bookings and cancels what it books.
"""
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
PASSWORD = "Smoke-Test-2026"


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        return next((c.value for c in self.jar if c.name == "qf_csrf"), None)

    def call(self, method, path, body=None, expect=None, headers=None):
        req = urllib.request.Request(BASE + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", BASE)
        if method not in ("GET", "HEAD") and self.csrf():
            req.add_header("X-CSRF-Token", self.csrf())
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with self.opener.open(req, timeout=30) as r:
                status, data = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, data = e.code, e.read()
        payload = json.loads(data) if data else None
        ok = status in expect if expect else 200 <= status < 300
        print(f"{'PASS' if ok else 'FAIL'} {method} {path} -> {status}")
        if not ok:
            print("     ", payload)
            sys.exit(1)
        return payload


def register(client, tag, **extra):
    return client.call("POST", "/api/auth/register", {
        "email": f"smoke{tag}@example.com", "password": PASSWORD, "confirm_password": PASSWORD,
        "full_name": "Smoke Tester", **extra}, expect={201, 403})


def main():
    tag = str(int(time.time()))
    anon = Client()
    health = anon.call("GET", "/api/health")
    assert health["database"] == "up" and health["redis"] == "up", health

    escalate = Client()
    assert escalate.call("POST", "/api/auth/register", {
        "email": f"esc{tag}@example.com", "password": PASSWORD, "confirm_password": PASSWORD,
        "full_name": "Escalation", "role": "ADMIN"}, expect={403}) is not None

    customer = Client()
    assert register(customer, tag)["user"]["role"] == "CUSTOMER"
    assert not any(c.name == "qf_session" and not c.has_nonstandard_attr("HttpOnly") for c in customer.jar), \
        "session cookie must be HttpOnly"

    hospitals = anon.call("GET", "/api/venues?kind=HOSPITAL&specialization=cardiology")["items"]
    assert hospitals, "no cardiology hospitals: seed sample data first"
    venue = anon.call("GET", f"/api/venues/{hospitals[0]['id']}")
    offering = next(o for o in venue["offerings"] if o["specialization_id"])
    slots = []
    for days in range(1, 8):
        day = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
        slots = anon.call("GET", f"/api/venues/{venue['id']}/slots?offering_id={offering['id']}&date={day}")
        if slots:
            break
    assert slots, "no free slots in the next week"
    body = {"venue_id": venue["id"], "offering_id": offering["id"], "provider_id": slots[0]["provider_id"],
            "start_at": slots[0]["start_at"]}
    key = {"Idempotency-Key": f"smoke-{tag}"}
    booking = customer.call("POST", "/api/bookings", body, expect={201}, headers=key)
    again = customer.call("POST", "/api/bookings", body, expect={200}, headers=key)
    assert again["reference"] == booking["reference"]
    print(f"     booked {booking['reference']} token {booking['token_label']}")

    other = Client()
    register(other, tag + "b")
    other.call("GET", f"/api/bookings/{booking['reference']}", expect={404})
    other.call("POST", "/api/bookings", body, expect={409})
    customer.call("POST", f"/api/bookings/{booking['reference']}/cancel")

    hotels = anon.call("GET", "/api/venues?kind=HOTEL")["items"]
    if hotels:
        check_in = date.today() + timedelta(days=10)
        quotes = anon.call("GET", f"/api/venues/{hotels[0]['id']}/rooms?check_in={check_in}"
                                  f"&check_out={check_in + timedelta(days=2)}&guests=2")
        quote = next(q for q in quotes if q["available"])
        reservation = customer.call("POST", "/api/reservations", {
            "venue_id": hotels[0]["id"], "room_type_id": quote["room_type_id"], "check_in": str(check_in),
            "check_out": str(check_in + timedelta(days=2)), "guests": 2, "total": "1.00"}, expect={422})
        reservation = customer.call("POST", "/api/reservations", {
            "venue_id": hotels[0]["id"], "room_type_id": quote["room_type_id"], "check_in": str(check_in),
            "check_out": str(check_in + timedelta(days=2)), "guests": 2}, expect={201})
        assert reservation["total"] == quote["total"], "server price mismatch"
        customer.call("POST", f"/api/reservations/{reservation['reference']}/cancel")

    status = anon.call("GET", "/api/wayzen/status")
    reply = customer.call("POST", "/api/wayzen/chat", {"message": "How do I cancel an appointment?"})
    assert reply["message"]["sources"], "Wayzen returned no sources; run python -m app.rag.ingest"
    print(f"     Wayzen mode={status['mode']}, top source: {reply['message']['sources'][0]['title']}")

    customer.call("POST", "/api/auth/logout", expect={204})
    customer.call("GET", "/api/auth/me", expect={401})
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
