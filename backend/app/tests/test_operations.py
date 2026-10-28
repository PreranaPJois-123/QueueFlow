"""Staff queue operations, venue-scoped authorization, wait estimates, turn
alerts, realtime delivery and admin role management."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.models import Notification, NotificationType, User, UserRole
from app.models.venues import Booking, BookingStatus, QueueDay, Venue, VenueStaff
from app.services.booking import queue_ops
from app.services.booking.common import local_today
from app.tests.conftest import TestSessionLocal, register_and_login
from app.tests.helpers import first_slot, next_working_day, offering_id, provider_id, seeded

GREENLEAF = "Greenleaf Multispeciality Hospital"


@pytest.fixture
def venues():
    return seeded()


def assign(venue_id, email):
    with TestSessionLocal() as db:
        user = db.query(User).filter_by(email=email).one()
        db.add(VenueStaff(venue_id=venue_id, user_id=user.id))
        db.commit()


def make_today_queue(venue_id, doctor_name, offsets, customers):
    """Insert today's bookings directly (independent of the wall clock)."""
    with TestSessionLocal() as db:
        venue = db.get(Venue, venue_id)
        doctor = provider_id(venue_id, doctor_name)
        offering = offering_id(venue_id, "General physician consultation")
        day = local_today(venue)
        queue = QueueDay(provider_id=doctor, service_date=day, next_token=len(offsets) + 1)
        db.add(queue)
        db.flush()
        now = datetime.now(timezone.utc)
        ids = []
        for i, (minutes, email) in enumerate(zip(offsets, customers, strict=True), start=1):
            user = db.query(User).filter_by(email=email).one()
            start = now + timedelta(minutes=minutes)
            booking = Booking(reference=f"QF-H-TEST{i:03d}", customer_id=user.id, venue_id=venue_id,
                              offering_id=offering, provider_id=doctor, queue_day_id=queue.id, start_at=start,
                              end_at=start + timedelta(minutes=15), service_date=day, token_number=i,
                              token_label=f"GM1-{i:03d}", status=BookingStatus.CONFIRMED)
            db.add(booking)
            db.flush()
            ids.append(booking.id)
        db.commit()
        return doctor, day, ids, queue.id


def test_staff_must_be_assigned_to_venue(client, venues):
    staff = register_and_login(client, "nurse@example.com", role="STAFF")
    customer = register_and_login(client, "pat@example.com")
    venue = venues[GREENLEAF]
    assert client.get("/api/ops/venues", headers=staff).json() == []
    assert client.get(f"/api/ops/venues/{venue}/queue", headers=staff).status_code == 403
    assert client.get(f"/api/ops/venues/{venue}/queue", headers=customer).status_code == 403
    assign(venue, "nurse@example.com")
    assert [v["id"] for v in client.get("/api/ops/venues", headers=staff).json()] == [venue]
    assert client.get(f"/api/ops/venues/{venue}/queue", headers=staff).status_code == 200
    other = venues["Riverside General Hospital"]
    assert client.get(f"/api/ops/venues/{other}/queue", headers=staff).status_code == 403


def test_queue_flow_estimates_and_alerts(client, venues, db_session):
    staff = register_and_login(client, "desk@example.com", role="STAFF")
    emails = [f"q{i}@example.com" for i in range(3)]
    customers = [register_and_login(client, e) for e in emails]
    venue = venues[GREENLEAF]
    assign(venue, "desk@example.com")
    doctor, day, ids, queue_id = make_today_queue(venue, "Dr. Ananya Rao", [5, 20, 40], emails)

    detail = client.get("/api/bookings/QF-H-TEST003", headers=customers[2]).json()
    assert detail["live"]["position"] == 3 and detail["live"]["eta_minutes"] >= 39

    started = client.post(f"/api/ops/providers/{doctor}/queue/{day}/next", headers=staff)
    assert started.status_code == 200 and started.json()["reference"] == "QF-H-TEST001"
    assert client.post(f"/api/ops/bookings/{ids[1]}/start", headers=staff).status_code == 409  # one at a time
    board = client.get(f"/api/ops/venues/{venue}/queue", headers=staff).json()
    row = next(p for p in board["providers"] if p["provider_id"] == doctor)
    assert row["current_token"] == "GM1-001" and row["waiting"] == 2

    # Customer 2 is ~20 minutes out -> exactly one turn alert, even after repeated recomputation.
    with TestSessionLocal() as db:
        queue_ops.refresh_queue_day(db, queue_id)
        db.commit()
        queue_ops.run_monitor_once(db)
    alerts = db_session.query(Notification).filter_by(type=NotificationType.TURN_APPROACHING).all()
    assert [a.booking_id for a in alerts] == [ids[1]]
    assert "approximately" in alerts[0].message or "shortly" in alerts[0].message
    assert db_session.query(Notification).filter_by(type=NotificationType.CALLED, booking_id=ids[0]).count() == 1

    # Delay notifications: once per delay value per booking
    for _ in range(2):
        assert client.post(f"/api/ops/providers/{doctor}/queue/{day}", headers=staff,
                           json={"delay_minutes": 15}).status_code == 200
    assert db_session.query(Notification).filter_by(type=NotificationType.SERVICE_DELAY).count() == 2
    delayed = client.get("/api/bookings/QF-H-TEST003", headers=customers[2]).json()["live"]
    assert delayed["delay_minutes"] == 15 and delayed["eta_minutes"] >= 54

    assert client.post(f"/api/ops/bookings/{ids[0]}/complete", headers=staff).json()["status"] == "COMPLETED"
    assert client.post(f"/api/ops/bookings/{ids[2]}/no-show", headers=staff).json()["status"] == "NO_SHOW"
    assert client.post(f"/api/ops/bookings/{ids[2]}/start", headers=staff).status_code == 409  # invalid transition
    paused = client.post(f"/api/ops/providers/{doctor}/queue/{day}", headers=staff, json={"paused": True})
    assert paused.json()["status"] == "PAUSED"
    assert client.post(f"/api/ops/bookings/{ids[1]}/start", headers=staff).status_code == 409
    # Customers cannot drive staff transitions
    assert client.post(f"/api/ops/bookings/{ids[1]}/check-in", headers=customers[1]).status_code == 403


def test_customer_cannot_see_other_customers_in_queue(client, venues):
    emails = ["v1@example.com", "v2@example.com"]
    c1 = register_and_login(client, emails[0])
    register_and_login(client, emails[1])
    make_today_queue(venues[GREENLEAF], "Dr. Ananya Rao", [10, 30], emails)
    body = client.get("/api/bookings/QF-H-TEST001", headers=c1).text
    assert "v2@example.com" not in body and "QF-H-TEST002" not in body
    assert client.get("/api/bookings/QF-H-TEST002", headers=c1).status_code == 404


def test_user_websocket_requires_session_and_delivers_private_events(client, venues):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws") as ws:
            ws.receive_json()
    customer = register_and_login(client, "ws@example.com")
    other = register_and_login(client, "ws2@example.com")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws", headers={"Cookie": customer["Cookie"],
                                                          "Origin": "https://evil.example"}) as ws:
            ws.receive_json()
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "ENT consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    with client.websocket_connect("/api/ws", headers={"Cookie": customer["Cookie"]}) as mine, \
            client.websocket_connect("/api/ws", headers={"Cookie": other["Cookie"]}) as theirs:
        assert mine.receive_json()["type"] == "hello" and theirs.receive_json()["type"] == "hello"
        resp = client.post("/api/bookings", headers=customer, json={"venue_id": venue, "offering_id": offering,
                                                                    "provider_id": slot["provider_id"],
                                                                    "start_at": slot["start_at"]})
        assert resp.status_code == 201
        # Future-day booking: a confirmation notification, but no live queue update yet.
        assert mine.receive_json()["type"] == "notification"
        theirs.send_text("ping")
        assert theirs.receive_json()["type"] == "pong"  # nothing of the other user's queued ahead of pong
        mine.send_text("x" * 200)  # oversized / non-protocol frames close the socket
        with pytest.raises(WebSocketDisconnect):
            mine.receive_json()


def test_notifications_api(client, venues):
    customer = register_and_login(client, "notes@example.com")
    other = register_and_login(client, "notes2@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "ENT consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    client.post("/api/bookings", headers=customer, json={"venue_id": venue, "offering_id": offering,
                                                         "provider_id": slot["provider_id"],
                                                         "start_at": slot["start_at"]})
    listing = client.get("/api/notifications", headers=customer).json()
    assert listing["unread"] == 1
    nid = listing["items"][0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=other).status_code == 404
    assert client.post(f"/api/notifications/{nid}/read", headers=customer).status_code == 200
    assert client.get("/api/notifications", headers=customer).json()["unread"] == 0
    prefs = client.patch("/api/auth/me", headers=customer, json={"pref_sound_enabled": True}).json()
    assert prefs["pref_sound_enabled"] is True


def test_admin_role_management_and_escalation_guards(client, venues, db_session):
    admin = register_and_login(client, "root@example.com", role="ADMIN")
    staff = register_and_login(client, "helper@example.com", role="STAFF")
    customer = register_and_login(client, "plain@example.com")
    target = db_session.query(User).filter_by(email="plain@example.com").one()
    assert client.patch(f"/api/admin/users/{target.id}", headers=customer, json={"role": "ADMIN"}).status_code == 403
    assert client.patch(f"/api/admin/users/{target.id}", headers=staff, json={"role": "ADMIN"}).status_code == 403
    me = db_session.query(User).filter_by(email="root@example.com").one()
    assert client.patch(f"/api/admin/users/{me.id}", headers=admin, json={"role": "STAFF"}).status_code == 422
    promoted = client.patch(f"/api/admin/users/{target.id}", headers=admin, json={"role": "STAFF"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "STAFF"
    assert client.get("/api/auth/me", headers=customer).status_code == 401  # sessions revoked on role change
    venue = venues[GREENLEAF]
    assert client.post(f"/api/admin/venues/{venue}/staff", headers=admin,
                       json={"user_id": target.id}).status_code == 201
    created = client.post("/api/admin/venues", headers=admin, json={"kind": "SHOP", "name": "Test Repair Desk",
                                                                    "city": "Pune", "timezone": "Asia/Kolkata"})
    assert created.status_code == 201 and created.json()["is_sample"] is False
    assert client.post("/api/admin/venues", headers=staff, json={"kind": "SHOP", "name": "Nope", "city": "Pune"}) \
        .status_code == 403
    bad_tz = client.post("/api/admin/venues", headers=admin, json={"kind": "SHOP", "name": "Bad", "city": "Pune",
                                                                   "timezone": "Mars/Base"})
    assert bad_tz.status_code == 422
    db_session.expire_all()
    assert db_session.query(User).filter_by(email="plain@example.com").one().role == UserRole.STAFF


def test_admin_configures_provider_and_slots_follow(client, venues):
    admin = register_and_login(client, "cfg@example.com", role="ADMIN")
    salon = venues["Bloom Unisex Salon"]
    haircut = offering_id(salon, "Haircut")
    resp = client.post(f"/api/admin/venues/{salon}/providers", headers=admin, json={
        "name": "Meena", "title": "Stylist", "token_prefix": "MN", "offering_ids": [haircut],
        "schedules": [{"weekday": next_working_day().weekday(), "start_time": "10:00", "end_time": "11:00"}]})
    assert resp.status_code == 201, resp.text
    slots = client.get(f"/api/venues/{salon}/slots", params={"offering_id": haircut,
                       "date": next_working_day().isoformat(), "provider_id": resp.json()["id"]}).json()
    assert len(slots) == 2  # two 30-minute haircuts in a one-hour window
    other_venue_offering = offering_id(venues[GREENLEAF], "ENT consultation")
    bad = client.post(f"/api/admin/venues/{salon}/providers", headers=admin, json={
        "name": "X", "token_prefix": "XX", "offering_ids": [other_venue_offering]})
    assert bad.status_code == 422
    dup = client.post(f"/api/admin/venues/{salon}/providers", headers=admin, json={"name": "Dup", "token_prefix": "MN"})
    assert dup.status_code == 409
