from app.tests.conftest import register_and_login


def test_customer_cannot_create_service(client):
    headers = register_and_login(client, "cust1@example.com", role="CUSTOMER")
    resp = client.post("/api/services", json={"name": "X"}, headers=headers)
    assert resp.status_code == 403


def test_staff_can_create_service(client):
    headers = register_and_login(client, "staff1@example.com", role="STAFF")
    resp = client.post("/api/services", json={"name": "X"}, headers=headers)
    assert resp.status_code == 201


def test_admin_can_create_service(client):
    headers = register_and_login(client, "admin1@example.com", role="ADMIN")
    resp = client.post("/api/services", json={"name": "X"}, headers=headers)
    assert resp.status_code == 201


def test_customer_cannot_call_next(client):
    staff_headers = register_and_login(client, "staff2@example.com", role="STAFF")
    svc = client.post("/api/services", json={"name": "Svc"}, headers=staff_headers).json()
    queue = client.post("/api/queues", json={"service_id": svc["id"], "name": "Q"}, headers=staff_headers).json()

    cust_headers = register_and_login(client, "cust2@example.com", role="CUSTOMER")
    resp = client.post(f"/api/staff/queues/{queue['id']}/next", headers=cust_headers)
    assert resp.status_code == 403


def test_unauthenticated_cannot_join_queue(client):
    staff_headers = register_and_login(client, "staff3@example.com", role="STAFF")
    svc = client.post("/api/services", json={"name": "Svc"}, headers=staff_headers).json()
    queue = client.post("/api/queues", json={"service_id": svc["id"], "name": "Q"}, headers=staff_headers).json()

    resp = client.post(f"/api/queues/{queue['id']}/join")
    assert resp.status_code == 401


def test_customer_cannot_cancel_others_ticket(client):
    staff_headers = register_and_login(client, "staff4@example.com", role="STAFF")
    svc = client.post("/api/services", json={"name": "Svc"}, headers=staff_headers).json()
    queue = client.post("/api/queues", json={"service_id": svc["id"], "name": "Q"}, headers=staff_headers).json()

    cust_a = register_and_login(client, "custA@example.com", role="CUSTOMER")
    cust_b = register_and_login(client, "custB@example.com", role="CUSTOMER")

    ticket = client.post(f"/api/queues/{queue['id']}/join", headers=cust_a).json()["ticket"]

    resp = client.post(f"/api/tickets/{ticket['id']}/cancel", headers=cust_b)
    assert resp.status_code == 403
