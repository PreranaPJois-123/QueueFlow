import time
from app.tests.conftest import register_and_login


def _make_queue(client, staff_headers, name="Q"):
    svc = client.post("/api/services", json={"name": f"Service-{name}"}, headers=staff_headers).json()
    return client.post("/api/queues", json={"service_id": svc["id"], "name": name}, headers=staff_headers).json()


def test_wait_estimate_uses_default_before_history(client):
    staff = register_and_login(client, "wt1staff@example.com", role="STAFF")
    queue = _make_queue(client, staff, "WT1")
    c1 = register_and_login(client, "wt1c1@example.com")
    c2 = register_and_login(client, "wt1c2@example.com")

    client.post(f"/api/queues/{queue['id']}/join", headers=c1)
    t2 = client.post(f"/api/queues/{queue['id']}/join", headers=c2).json()

    # DEFAULT_AVG_SERVICE_MINUTES=5, 1 person ahead => 5 minutes
    assert t2["estimated_wait_minutes"] == 5


def test_serving_a_ticket_creates_service_record(client, db_session):
    staff = register_and_login(client, "wt2staff@example.com", role="STAFF")
    queue = _make_queue(client, staff, "WT2")
    cust = register_and_login(client, "wt2c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    client.post(f"/api/staff/tickets/{ticket['id']}/serve", headers=staff)

    from app.models.models import ServiceRecord
    records = db_session.query(ServiceRecord).filter(ServiceRecord.ticket_id == ticket["id"]).all()
    assert len(records) == 1
    assert records[0].outcome.value == "SERVED"


def test_analytics_requires_staff_role(client):
    cust = register_and_login(client, "an1@example.com", role="CUSTOMER")
    resp = client.get("/api/analytics", headers=cust)
    assert resp.status_code == 403


def test_analytics_reflects_served_tickets(client):
    staff = register_and_login(client, "an2staff@example.com", role="STAFF")
    queue = _make_queue(client, staff, "AN2")
    cust = register_and_login(client, "an2c1@example.com")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust).json()["ticket"]
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    client.post(f"/api/staff/tickets/{ticket['id']}/serve", headers=staff)

    resp = client.get("/api/analytics", headers=staff)
    assert resp.status_code == 200
    data = resp.json()
    assert data["customers_served_today"] >= 1
    assert data["active_queues"] >= 1


def test_analytics_empty_state_has_no_negative_or_null_crash(client):
    staff = register_and_login(client, "an3staff@example.com", role="STAFF")
    resp = client.get("/api/analytics", headers=staff)
    assert resp.status_code == 200
    data = resp.json()
    assert data["customers_served_today"] == 0
    assert data["average_wait_minutes"] == 0


def test_health_endpoint(client, monkeypatch):
    from app.core.redis_client import redis_client
    monkeypatch.setattr(redis_client, "ping", lambda: True)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database"] == "up"
    assert body["redis"] == "up"
