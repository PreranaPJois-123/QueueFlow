#!/usr/bin/env python3
"""End-to-end smoke test against a running QueueFlow deployment (stdlib only).

Usage:
  QF_ADMIN_EMAIL=... QF_ADMIN_PASSWORD=... python3 scripts/smoke_test.py http://HOST

Exercises: health, admin login, service + queue creation, customer registration,
privilege-escalation rejection, join queue, staff call-next/serve, ticket status.
Creates uniquely named test records; it never deletes or modifies existing data.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")


def call(method, path, body=None, token=None, expect=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
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


def main():
    email, password = os.environ.get("QF_ADMIN_EMAIL"), os.environ.get("QF_ADMIN_PASSWORD")
    if not email or not password:
        sys.exit("Set QF_ADMIN_EMAIL and QF_ADMIN_PASSWORD (an existing STAFF/ADMIN account)")
    tag = str(int(time.time()))

    health = call("GET", "/api/health")
    assert health["database"] == "up" and health["redis"] == "up", health

    staff = call("POST", "/api/auth/login", {"email": email, "password": password})["access_token"]
    service = call("POST", "/api/services", {"name": f"Smoke Service {tag}"}, staff, expect={201})
    queue = call("POST", "/api/queues", {"service_id": service["id"], "name": f"Smoke Queue {tag}"},
                 staff, expect={201})

    cust_email = f"smoke{tag}@example.com"
    escalated = call("POST", "/api/auth/register", {"email": f"esc{tag}@example.com", "password": "Passw0rd!x",
                     "full_name": "Escalation Attempt", "role": "ADMIN"}, expect={201, 400, 403, 422})
    assert not (isinstance(escalated, dict) and escalated.get("role") == "ADMIN"), "public registration granted ADMIN"
    call("POST", "/api/auth/register", {"email": cust_email, "password": "Passw0rd!x", "full_name": "Smoke Customer"},
         expect={201})
    customer = call("POST", "/api/auth/login", {"email": cust_email, "password": "Passw0rd!x"})["access_token"]

    call("POST", "/api/services", {"name": "should fail"}, customer, expect={403})
    services = call("GET", "/api/services", token=customer)
    assert any(s["id"] == service["id"] for s in services), "new service not listed for customer"

    ticket = call("POST", f"/api/queues/{queue['id']}/join", {}, customer, expect={201})["ticket"]
    called = call("POST", f"/api/staff/queues/{queue['id']}/next", token=staff)
    assert called["id"] == ticket["id"], "call-next returned a different ticket"
    call("POST", f"/api/staff/tickets/{ticket['id']}/serve", token=staff)
    final = call("GET", f"/api/tickets/{ticket['id']}", token=customer)
    assert final["ticket"]["status"] == "SERVED", final["ticket"]["status"]
    mine = call("GET", "/api/tickets/mine", token=customer)
    assert any(t["id"] == ticket["id"] for t in mine)
    print(f"ALL CHECKS PASSED (service={service['id']}, queue={queue['id']}, ticket={ticket['id']})")


if __name__ == "__main__":
    main()
