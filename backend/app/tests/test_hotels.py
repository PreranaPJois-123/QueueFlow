"""Hotel availability, server pricing, inventory and concurrency."""
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.models import User
from app.models.venues import Reservation, RoomInventory, RoomType
from app.services.booking import hotels
from app.tests.conftest import TestSessionLocal, register_and_login
from app.tests.helpers import next_working_day, room_type_id, seeded

PALM = "Palm Courtyard Hotel"


@pytest.fixture
def venues():
    return seeded()


def reserve(client, headers, venue, room_type, check_in, nights=2, guests=2, key=None, **extra):
    h = {**headers, **({"Idempotency-Key": key} if key else {})}
    return client.post("/api/reservations", headers=h, json={
        "venue_id": venue, "room_type_id": room_type, "check_in": check_in.isoformat(),
        "check_out": (check_in + timedelta(days=nights)).isoformat(), "guests": guests, **extra})


def test_quote_is_server_calculated(client, venues):
    venue = venues[PALM]
    check_in = next_working_day(3)
    quotes = client.get(f"/api/venues/{venue}/rooms", params={"check_in": check_in.isoformat(),
                        "check_out": (check_in + timedelta(days=3)).isoformat(), "guests": 2}).json()
    standard = next(q for q in quotes if q["room_type_name"] == "Standard Queen")
    assert Decimal(standard["subtotal"]) == Decimal("9600.00")  # 3200 x 3 nights
    assert Decimal(standard["taxes"]) == Decimal("1152.00")     # 12%
    assert Decimal(standard["total"]) == Decimal("10752.00")
    assert standard["rooms_left"] == 10 and standard["available"]
    # Party of 4 only fits the family suite
    family = client.get(f"/api/venues/{venue}/rooms", params={"check_in": check_in.isoformat(),
                        "check_out": (check_in + timedelta(days=1)).isoformat(), "guests": 4}).json()
    assert [q["room_type_name"] for q in family] == ["Family Suite"]


def test_reservation_end_to_end_and_client_price_ignored(client, venues):
    guest = register_and_login(client, "guest@example.com")
    venue, rt = venues[PALM], room_type_id(venues[PALM], "Deluxe Twin")
    resp = reserve(client, guest, venue, rt, next_working_day(5), special_requests="Late arrival")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reference"].startswith("QF-R-") and body["total"] == "9184.00"  # 4100 x 2 x 1.12
    # A client-supplied price is not accepted
    assert reserve(client, guest, venue, rt, next_working_day(9), total="1.00").status_code == 422
    assert [r["reference"] for r in client.get("/api/reservations", headers=guest).json()] == [body["reference"]]


@pytest.mark.parametrize("offset,nights,guests,code", [(-2, 2, 2, 422), (3, 0, 2, 422), (3, 31, 2, 422),
                                                        (3, 2, 3, 422), (400, 2, 2, 422)])
def test_invalid_stays_rejected(client, venues, offset, nights, guests, code):
    guest = register_and_login(client, "invalid@example.com")
    venue, rt = venues[PALM], room_type_id(venues[PALM], "Standard Queen")
    from datetime import datetime
    from zoneinfo import ZoneInfo
    check_in = datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=offset)
    assert reserve(client, guest, venue, rt, check_in, nights=nights, guests=guests).status_code == code


def test_inventory_enforced_last_room(client, venues, db_session):
    venue, rt = venues["Hilltop Residency"], room_type_id(venues["Hilltop Residency"], "Heritage Suite")  # 1 room
    check_in = next_working_day(4)
    a, b = register_and_login(client, "ha@example.com"), register_and_login(client, "hb@example.com")
    assert reserve(client, a, venue, rt, check_in, nights=3).status_code == 201
    overlapping = reserve(client, b, venue, rt, check_in + timedelta(days=2), nights=2)
    assert overlapping.status_code == 409 and "sold out" in overlapping.json()["detail"]
    # Back-to-back stay (check-in on the other guest's check-out day) is fine
    assert reserve(client, b, venue, rt, check_in + timedelta(days=3), nights=1).status_code == 201
    # A failed attempt leaves no partial inventory behind
    nights = {r.night: r.booked for r in db_session.query(RoomInventory).all()}
    assert set(nights.values()) == {1}


def test_concurrent_last_room_never_overbooked(client, venues, db_session):
    venue, rt = venues["Hilltop Residency"], room_type_id(venues["Hilltop Residency"], "Heritage Suite")
    check_in = next_working_day(6)
    for i in range(6):
        register_and_login(client, f"room{i}@example.com")
    barrier, results = threading.Barrier(6), []

    def attempt(i):
        barrier.wait()
        with TestSessionLocal() as db:
            user = db.query(User).filter_by(email=f"room{i}@example.com").one()
            try:
                results.append(hotels.create_reservation(db, user, venue_id=venue, room_type_id=rt,
                                                         check_in=check_in, check_out=check_in + timedelta(days=2),
                                                         guests=2)[0].reference)
            except HTTPException as error:
                results.append(error.status_code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(isinstance(r, str) for r in results) == 1 and results.count(409) == 5, results
    assert all(r.booked == 1 for r in db_session.query(RoomInventory).all())


def test_idempotent_reservation(client, venues, db_session):
    guest = register_and_login(client, "idemh@example.com")
    venue, rt = venues[PALM], room_type_id(venues[PALM], "Standard Queen")
    first = reserve(client, guest, venue, rt, next_working_day(3), key="hotel-key-0001")
    second = reserve(client, guest, venue, rt, next_working_day(3), key="hotel-key-0001")
    assert (first.status_code, second.status_code) == (201, 200)
    assert db_session.query(Reservation).count() == 1
    assert db_session.query(RoomInventory).first().booked == 1


def test_cancel_free_and_late(client, venues, db_session):
    guest = register_and_login(client, "cancelh@example.com")
    venue, rt = venues[PALM], room_type_id(venues[PALM], "Standard Queen")
    early = reserve(client, guest, venue, rt, next_working_day(10)).json()
    terms = client.get(f"/api/reservations/{early['reference']}/cancellation-terms", headers=guest).json()
    assert terms["late"] is False
    cancelled = client.post(f"/api/reservations/{early['reference']}/cancel", headers=guest).json()
    assert cancelled["status"] == "CANCELLED" and cancelled["cancellation_fee"] == "0.00"
    assert all(r.booked == 0 for r in db_session.query(RoomInventory).all())  # inventory released
    late = reserve(client, guest, venue, rt, next_working_day(2)).json()
    db_session.query(RoomType).filter_by(id=rt).one().venue.free_cancellation_hours = 720
    db_session.commit()
    charged = client.post(f"/api/reservations/{late['reference']}/cancel", headers=guest).json()
    assert charged["cancellation_fee"] == "3200.00"


def test_modify_reservation_atomic(client, venues, db_session):
    guest, other = register_and_login(client, "modh@example.com"), register_and_login(client, "blocker@example.com")
    venue = venues["Hilltop Residency"]
    suite, garden = room_type_id(venue, "Heritage Suite"), room_type_id(venue, "Garden Room")
    start = next_working_day(5)
    ref = reserve(client, guest, venue, garden, start, nights=2).json()["reference"]
    reserve(client, other, venue, suite, start + timedelta(days=10), nights=1)  # suite sold for that night
    blocked = client.post(f"/api/reservations/{ref}/modify", headers=guest, json={
        "check_in": (start + timedelta(days=10)).isoformat(), "check_out": (start + timedelta(days=11)).isoformat(),
        "guests": 2, "room_type_id": suite})
    assert blocked.status_code == 409
    unchanged = client.get(f"/api/reservations/{ref}", headers=guest).json()
    assert unchanged["room_type_id"] == garden and unchanged["check_in"] == start.isoformat()
    ok = client.post(f"/api/reservations/{ref}/modify", headers=guest, json={
        "check_in": (start + timedelta(days=1)).isoformat(), "check_out": (start + timedelta(days=4)).isoformat(),
        "guests": 3, "room_type_id": suite})
    assert ok.status_code == 200 and ok.json()["nights"] == 3 and ok.json()["total"] == "17472.00"
    garden_rows = db_session.query(RoomInventory).filter_by(room_type_id=garden).all()
    assert all(r.booked == 0 for r in garden_rows)


def test_reservation_isolation(client, venues):
    owner, other = register_and_login(client, "rown@example.com"), register_and_login(client, "roth@example.com")
    venue, rt = venues[PALM], room_type_id(venues[PALM], "Standard Queen")
    ref = reserve(client, owner, venue, rt, next_working_day(3)).json()["reference"]
    for method, path in [("get", f"/api/reservations/{ref}"), ("post", f"/api/reservations/{ref}/cancel"),
                         ("get", f"/api/reservations/{ref}/cancellation-terms")]:
        assert getattr(client, method)(path, headers=other).status_code == 404
