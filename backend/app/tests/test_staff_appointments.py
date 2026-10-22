from datetime import datetime, timedelta, timezone

from app.tests.conftest import register_and_login


def test_staff_can_process_real_customer_booking(client):
    staff = register_and_login(client, "staff-bookings@example.com", role="STAFF")
    customer = register_and_login(client, "customer-bookings@example.com", full_name="Booked Customer")
    service = client.post("/api/services", headers=staff, json={"name": "Consultation"}).json()
    booking = client.post("/api/appointments", headers=customer, json={
        "service_id": service["id"],
        "scheduled_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    })
    assert booking.status_code == 201
    booking_id = booking.json()["id"]

    assert client.get("/api/staff/appointments", headers=customer).status_code == 403
    rows = client.get("/api/staff/appointments", headers=staff)
    assert rows.status_code == 200
    assert rows.json()[0]["customer_name"] == "Booked Customer"
    assert rows.json()[0]["service_name"] == "Consultation"

    assert client.post(f"/api/staff/appointments/{booking_id}/check-in", headers=customer).status_code == 403
    assert client.post(f"/api/staff/appointments/{booking_id}/check-in", headers=staff).json()["status"] == "CHECKED_IN"
    assert client.post(f"/api/staff/appointments/{booking_id}/no-show", headers=staff).status_code == 409
    assert client.post(f"/api/staff/appointments/{booking_id}/complete", headers=staff).json()["status"] == "COMPLETED"
    assert client.get("/api/appointments", headers=customer).json()[0]["status"] == "COMPLETED"
