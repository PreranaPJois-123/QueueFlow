import pytest
from app.tests.conftest import register_and_login


def _make_queue(client, staff_headers, name="Q"):
    svc = client.post("/api/services", json={"name": f"Service-{name}"}, headers=staff_headers).json()
    return client.post("/api/queues", json={"service_id": svc["id"], "name": name}, headers=staff_headers).json()


def test_join_queue_assigns_sequential_tokens(client):
    staff = register_and_login(client, "staffq1@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q1")

    c1 = register_and_login(client, "q1c1@example.com")
    c2 = register_and_login(client, "q1c2@example.com")

    t1 = client.post(f"/api/queues/{queue['id']}/join", headers=c1).json()["ticket"]
    t2 = client.post(f"/api/queues/{queue['id']}/join", headers=c2).json()["ticket"]

    assert t1["token_label"] == "A001"
    assert t2["token_label"] == "A002"


def test_cannot_join_same_queue_twice_while_active(client):
    staff = register_and_login(client, "staffq2@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q2")
    cust = register_and_login(client, "q2c1@example.com")

    r1 = client.post(f"/api/queues/{queue['id']}/join", headers=cust)
    assert r1.status_code == 201
    r2 = client.post(f"/api/queues/{queue['id']}/join", headers=cust)
    assert r2.status_code == 409


def test_call_next_on_empty_queue_fails(client):
    staff = register_and_login(client, "staffq3@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q3")

    resp = client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert resp.status_code == 409
    assert "empty" in resp.json()["detail"].lower()


def test_call_next_advances_waiting_ticket(client):
    staff = register_and_login(client, "staffq4@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q4")
    cust = register_and_login(client, "q4c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    resp = client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert resp.status_code == 200
    called = resp.json()
    assert called["id"] == ticket["id"]
    assert called["status"] == "CALLED"


def test_cannot_call_next_while_ticket_already_called(client):
    staff = register_and_login(client, "staffq5@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q5")
    c1 = register_and_login(client, "q5c1@example.com")
    c2 = register_and_login(client, "q5c2@example.com")

    client.post(f"/api/queues/{queue['id']}/join", headers=c1)
    client.post(f"/api/queues/{queue['id']}/join", headers=c2)

    r1 = client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert r1.status_code == 200

    r2 = client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert r2.status_code == 409


def test_serve_ticket_full_lifecycle(client):
    staff = register_and_login(client, "staffq6@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q6")
    cust = register_and_login(client, "q6c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)

    resp = client.post(f"/api/staff/tickets/{ticket['id']}/serve", headers=staff)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SERVED"


def test_cannot_serve_a_waiting_ticket_not_yet_called(client):
    staff = register_and_login(client, "staffq7@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q7")
    cust = register_and_login(client, "q7c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    resp = client.post(f"/api/staff/tickets/{ticket['id']}/serve", headers=staff)
    assert resp.status_code == 409


def test_cannot_serve_already_served_ticket(client):
    staff = register_and_login(client, "staffq8@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q8")
    cust = register_and_login(client, "q8c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    client.post(f"/api/staff/tickets/{ticket['id']}/serve", headers=staff)

    resp = client.post(f"/api/staff/tickets/{ticket['id']}/serve", headers=staff)
    assert resp.status_code == 409


def test_skip_ticket(client):
    staff = register_and_login(client, "staffq9@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q9")
    cust = register_and_login(client, "q9c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)

    resp = client.post(f"/api/staff/tickets/{ticket['id']}/skip", headers=staff)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SKIPPED"


def test_cannot_skip_nonexistent_ticket(client):
    staff = register_and_login(client, "staffq10@example.com", role="STAFF")
    resp = client.post("/api/staff/tickets/00000000-0000-0000-0000-000000000000/skip", headers=staff)
    assert resp.status_code == 404


def test_skipping_frees_queue_for_next_call(client):
    staff = register_and_login(client, "staffq11@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q11")
    c1 = register_and_login(client, "q11c1@example.com")
    c2 = register_and_login(client, "q11c2@example.com")

    t1 = client.post(f"/api/queues/{queue['id']}/join", headers=c1).json()["ticket"]
    t2 = client.post(f"/api/queues/{queue['id']}/join", headers=c2).json()["ticket"]

    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)  # calls t1
    client.post(f"/api/staff/tickets/{t1['id']}/skip", headers=staff)

    resp = client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert resp.status_code == 200
    assert resp.json()["id"] == t2["id"]


def test_people_ahead_and_wait_estimate(client):
    staff = register_and_login(client, "staffq12@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q12")
    c1 = register_and_login(client, "q12c1@example.com")
    c2 = register_and_login(client, "q12c2@example.com")
    c3 = register_and_login(client, "q12c3@example.com")

    client.post(f"/api/queues/{queue['id']}/join", headers=c1)
    client.post(f"/api/queues/{queue['id']}/join", headers=c2)
    t3 = client.post(f"/api/queues/{queue['id']}/join", headers=c3).json()

    assert t3["people_ahead"] == 2
    assert t3["estimated_wait_minutes"] > 0  # falls back to default avg service time


def test_cancel_waiting_ticket(client):
    staff = register_and_login(client, "staffq13@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q13")
    cust = register_and_login(client, "q13c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    resp = client.post(f"/api/tickets/{ticket['id']}/cancel", headers=cust)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"

    # cancelled customer can join again
    resp2 = client.post(f"/api/queues/{queue['id']}/join", headers=cust)
    assert resp2.status_code == 201


def test_cannot_cancel_already_called_ticket(client):
    staff = register_and_login(client, "staffq14@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q14")
    cust = register_and_login(client, "q14c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)

    resp = client.post(f"/api/tickets/{ticket['id']}/cancel", headers=cust)
    assert resp.status_code == 409


def test_pause_queue_blocks_join(client):
    staff = register_and_login(client, "staffq15@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q15")

    client.post(f"/api/staff/queues/{queue['id']}/pause", headers=staff)

    cust = register_and_login(client, "q15c1@example.com")
    resp = client.post(f"/api/queues/{queue['id']}/join", headers=cust)
    assert resp.status_code == 409


def test_resume_queue_allows_join_again(client):
    staff = register_and_login(client, "staffq16@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q16")

    client.post(f"/api/staff/queues/{queue['id']}/pause", headers=staff)
    client.post(f"/api/staff/queues/{queue['id']}/resume", headers=staff)

    cust = register_and_login(client, "q16c1@example.com")
    resp = client.post(f"/api/queues/{queue['id']}/join", headers=cust)
    assert resp.status_code == 201


def test_closed_queue_cannot_be_resumed(client):
    staff = register_and_login(client, "staffq17@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q17")

    client.post(f"/api/staff/queues/{queue['id']}/close", headers=staff)
    resp = client.post(f"/api/staff/queues/{queue['id']}/resume", headers=staff)
    assert resp.status_code == 409


def test_cannot_call_next_on_paused_queue(client):
    staff = register_and_login(client, "staffq18@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q18")
    cust = register_and_login(client, "q18c1@example.com")
    client.post(f"/api/queues/{queue['id']}/join", headers=cust)

    client.post(f"/api/staff/queues/{queue['id']}/pause", headers=staff)
    resp = client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert resp.status_code == 409


def test_duplicate_skip_on_already_skipped_ticket_fails(client):
    staff = register_and_login(client, "staffq19@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q19")
    cust = register_and_login(client, "q19c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    client.post(f"/api/staff/tickets/{ticket['id']}/skip", headers=staff)

    resp = client.post(f"/api/staff/tickets/{ticket['id']}/skip", headers=staff)
    assert resp.status_code == 409


def test_staff_queue_state_reflects_waiting_list(client):
    staff = register_and_login(client, "staffq20@example.com", role="STAFF")
    queue = _make_queue(client, staff, "Q20")
    c1 = register_and_login(client, "q20c1@example.com")
    c2 = register_and_login(client, "q20c2@example.com")

    client.post(f"/api/queues/{queue['id']}/join", headers=c1)
    client.post(f"/api/queues/{queue['id']}/join", headers=c2)

    resp = client.get(f"/api/staff/queues/{queue['id']}/state", headers=staff)
    assert resp.status_code == 200
    state = resp.json()
    assert state["waiting_count"] == 2
    assert state["next_ticket_label"] == "A001"
