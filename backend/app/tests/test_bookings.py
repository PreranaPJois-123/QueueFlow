"""Hospital and shop appointments: catalogue, slots, tokens, policies, isolation, concurrency."""
import threading
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.models import Notification, NotificationType, User
from app.models.venues import Booking, BookingStatus, QueueDay
from app.services.booking import appointments
from app.tests.conftest import TestSessionLocal, register_and_login
from app.tests.helpers import at, first_slot, next_working_day, offering_id, provider_id, seeded

GREENLEAF = "Greenleaf Multispeciality Hospital"


@pytest.fixture
def venues():
    return seeded()


def book(client, headers, venue, offering, slot, key=None, **extra):
    h = {**headers, **({"Idempotency-Key": key} if key else {})}
    return client.post("/api/bookings", headers=h, json={"venue_id": venue, "offering_id": offering,
                                                         "provider_id": slot["provider_id"],
                                                         "start_at": slot["start_at"], **extra})


def test_catalogue_search_and_filters(client, venues):
    hospitals = client.get("/api/venues", params={"kind": "HOSPITAL"}).json()
    assert hospitals["total"] == 3 and all(v["is_sample"] for v in hospitals["items"])
    assert client.get("/api/venues", params={"kind": "HOSPITAL", "city": "mysuru"}).json()["total"] == 1
    assert client.get("/api/venues", params={"q": "greenleaf"}).json()["items"][0]["name"] == GREENLEAF
    cardio = client.get("/api/venues", params={"kind": "HOSPITAL", "specialization": "cardiology"}).json()
    assert [v["name"] for v in cardio["items"]] == [GREENLEAF]
    assert client.get("/api/venues", params={"q": "%"}).json()["total"] == 0  # LIKE wildcards are escaped
    specs = [s["name"] for s in client.get("/api/specializations").json()]
    assert {"Cardiology", "Dermatology", "Pediatrics", "Ophthalmology"} <= set(specs)


def test_venue_detail_shows_only_configured_doctors(client, venues):
    detail = client.get(f"/api/venues/{venues[GREENLEAF]}").json()
    cardio = next(o for o in detail["offerings"] if o["name"] == "Cardiology consultation")
    doctors = [p["name"] for p in detail["providers"] if cardio["id"] in p["offering_ids"]]
    assert sorted(doctors) == ["Dr. Meera Iyer", "Dr. Vikram Shetty"]
    assert client.get("/api/venues/does-not-exist").status_code == 404


def test_hospital_booking_end_to_end(client, venues, db_session):
    customer = register_and_login(client, "patient@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Cardiology consultation")
    day = next_working_day()
    doctor = provider_id(venue, "Dr. Vikram Shetty")
    slots = first_slot(client, venue, offering, day, doctor)
    assert all(s["provider_id"] == doctor for s in slots)
    resp = book(client, customer, venue, offering, slots[0], notes="First visit")
    assert resp.status_code == 201, resp.text
    booking = resp.json()
    assert booking["reference"].startswith("QF-H-") and booking["token_label"] == "CAR1-001"
    assert booking["status"] == "CONFIRMED" and booking["specialization"] == "Cardiology"
    assert booking["live"] is None  # live position is only shown on the visit day
    # The slot disappears for everyone; the booking shows in the dashboard list.
    remaining = client.get(f"/api/venues/{venue}/slots", params={"offering_id": offering, "date": day.isoformat(),
                                                                  "provider_id": doctor}).json()
    assert slots[0]["start_at"] not in [s["start_at"] for s in remaining]
    mine = client.get("/api/bookings", headers=customer).json()
    assert [b["reference"] for b in mine] == [booking["reference"]]
    assert db_session.query(Notification).filter_by(type=NotificationType.BOOKING_CONFIRMED).count() == 1


def test_tokens_sequential_per_doctor_per_day(client, venues):
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Cardiology consultation")
    day = next_working_day()
    doctor = provider_id(venue, "Dr. Vikram Shetty")
    slots = first_slot(client, venue, offering, day, doctor)
    tokens = []
    for i in range(3):
        headers = register_and_login(client, f"p{i}@example.com")
        tokens.append(book(client, headers, venue, offering, slots[i]).json()["token_label"])
    assert tokens == ["CAR1-001", "CAR1-002", "CAR1-003"]
    other = provider_id(venue, "Dr. Meera Iyer")
    other_slot = first_slot(client, venue, offering, day, other)[0]
    headers = register_and_login(client, "p9@example.com")
    assert book(client, headers, venue, offering, other_slot).json()["token_label"] == "CAR2-001"


def test_any_available_provider(client, venues):
    customer = register_and_login(client, "any@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Cardiology consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    resp = client.post("/api/bookings", headers=customer, json={"venue_id": venue, "offering_id": offering,
                                                                "start_at": slot["start_at"]})
    assert resp.status_code == 201 and resp.json()["provider_id"] in {
        provider_id(venue, "Dr. Vikram Shetty"), provider_id(venue, "Dr. Meera Iyer")}


def test_invalid_booking_requests(client, venues):
    customer = register_and_login(client, "bad@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Cardiology consultation")
    day = next_working_day()
    derm = provider_id(venue, "Dr. Farah Khan")
    slot = first_slot(client, venue, offering, day)[0]
    # Doctor not authorised for this service
    assert book(client, customer, venue, offering, {**slot, "provider_id": derm}).status_code == 404
    # Service from another venue
    lotus = seeded  # noqa: F841 (already seeded)
    other_offering = offering_id(venues["Lotus Children & Family Clinic"], "Pediatric consultation")
    assert book(client, customer, venue, other_offering, slot).status_code == 404
    # Off-grid time (not a generated slot), naive datetime, past date, beyond horizon, Sunday
    assert book(client, customer, venue, offering, {**slot, "start_at": at(day, 9, 7).isoformat()}).status_code == 409
    assert book(client, customer, venue, offering, {**slot, "start_at": "2030-01-01T10:00:00"}).status_code == 422
    assert book(client, customer, venue, offering, {**slot, "start_at": at(day - timedelta(days=7), 9).isoformat()}) \
        .status_code == 422
    assert book(client, customer, venue, offering, {**slot, "start_at": at(day + timedelta(days=60), 9).isoformat()}) \
        .status_code == 422
    assert client.post("/api/bookings", json={}, headers=customer).status_code == 422
    assert client.post("/api/bookings", headers={}, json={"venue_id": venue, "offering_id": offering,
                                                          "start_at": slot["start_at"]}).status_code == 401


def test_double_booking_same_slot_rejected(client, venues):
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Dermatology consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    a, b = register_and_login(client, "a@example.com"), register_and_login(client, "b@example.com")
    assert book(client, a, venue, offering, slot).status_code == 201
    assert book(client, b, venue, offering, slot).status_code == 409


def test_customer_cannot_hold_overlapping_appointments(client, venues):
    customer = register_and_login(client, "overlap@example.com")
    venue = venues[GREENLEAF]
    day = next_working_day()
    derm = offering_id(venue, "Dermatology consultation")
    ent = offering_id(venue, "ENT consultation")
    slot = first_slot(client, venue, derm, day)[0]
    assert book(client, customer, venue, derm, slot).status_code == 201
    ent_slot = next(s for s in first_slot(client, venue, ent, day) if s["start_at"] == slot["start_at"])
    assert book(client, customer, venue, ent, ent_slot).status_code == 409


def test_idempotency_key_prevents_duplicate_booking(client, venues, db_session):
    customer = register_and_login(client, "idem@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "ENT consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    first = book(client, customer, venue, offering, slot, key="retry-key-0001")
    again = book(client, customer, venue, offering, slot, key="retry-key-0001")
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["reference"] == again.json()["reference"]
    assert db_session.query(Booking).count() == 1


def test_object_level_authorization(client, venues):
    owner, other = register_and_login(client, "owner@example.com"), register_and_login(client, "other@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "ENT consultation")
    ref = book(client, owner, venue, offering, first_slot(client, venue, offering, next_working_day())[0]).json()[
        "reference"]
    assert client.get(f"/api/bookings/{ref}", headers=other).status_code == 404
    assert client.post(f"/api/bookings/{ref}/cancel", headers=other).status_code == 404
    assert client.get("/api/bookings", headers=other).json() == []
    assert client.get(f"/api/bookings/{ref}", headers=owner).status_code == 200


def test_cancel_frees_slot_and_token_not_reused(client, venues):
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Neurology consultation")
    day = next_working_day()
    slot = first_slot(client, venue, offering, day)[0]
    a, b = register_and_login(client, "ca@example.com"), register_and_login(client, "cb@example.com")
    first = book(client, a, venue, offering, slot).json()
    cancelled = client.post(f"/api/bookings/{first['reference']}/cancel", headers=a)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert client.post(f"/api/bookings/{first['reference']}/cancel", headers=a).status_code == 409
    second = book(client, b, venue, offering, slot)
    assert second.status_code == 201 and second.json()["token_label"] == "NEU1-002"


def test_cancel_cutoff_enforced(client, venues, db_session):
    customer = register_and_login(client, "late@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "ENT consultation")
    ref = book(client, customer, venue, offering, first_slot(client, venue, offering, next_working_day())[0]).json()[
        "reference"]
    booking = db_session.query(Booking).filter_by(reference=ref).one()
    booking.venue.cancel_cutoff_minutes = 60 * 24 * 7
    db_session.commit()
    resp = client.post(f"/api/bookings/{ref}/cancel", headers=customer)
    assert resp.status_code == 409 and "contact" in resp.json()["detail"]


def test_reschedule_same_day_keeps_token_other_day_new_token(client, venues):
    customer = register_and_login(client, "move@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "Orthopedic consultation")
    day = next_working_day()
    slots = first_slot(client, venue, offering, day)
    booking = book(client, customer, venue, offering, slots[0]).json()
    moved = client.post(f"/api/bookings/{booking['reference']}/reschedule", headers=customer,
                        json={"start_at": slots[3]["start_at"]})
    assert moved.status_code == 200 and moved.json()["token_label"] == booking["token_label"]
    assert moved.json()["start_at"] != booking["start_at"]
    # The old slot is free again
    assert slots[0]["start_at"] in [s["start_at"] for s in first_slot(client, venue, offering, day)]
    later = next_working_day(2)
    new_slot = first_slot(client, venue, offering, later)[0]
    moved2 = client.post(f"/api/bookings/{booking['reference']}/reschedule", headers=customer,
                         json={"start_at": new_slot["start_at"]})
    assert moved2.status_code == 200 and moved2.json()["service_date"] == later.isoformat()
    assert moved2.json()["token_label"] == "ORT1-001"  # first token of the new day's queue


def test_shop_booking_respects_staff_authorisation(client, venues):
    customer = register_and_login(client, "shopper@example.com")
    salon = venues["Bloom Unisex Salon"]
    haircut, spa = offering_id(salon, "Haircut"), offering_id(salon, "Hair spa")
    ravi = provider_id(salon, "Ravi")
    assert client.get(f"/api/venues/{salon}/slots", params={"offering_id": spa, "date": next_working_day().isoformat(),
                                                            "provider_id": ravi}).status_code == 404
    slot = first_slot(client, salon, haircut, next_working_day(), ravi)[0]
    resp = book(client, customer, salon, haircut, slot)
    assert resp.status_code == 201 and resp.json()["reference"].startswith("QF-S-")
    assert resp.json()["token_label"] == "RV-001"


def test_service_duration_respected(client, venues):
    salon = venues["Bloom Unisex Salon"]
    spa = offering_id(salon, "Hair spa")
    asha = provider_id(salon, "Asha")
    slots = first_slot(client, salon, spa, next_working_day(), asha)
    from datetime import datetime
    starts = [datetime.fromisoformat(s["start_at"]) for s in slots]
    assert all((b - a).total_seconds() >= 45 * 60 for a, b in zip(starts, starts[1:], strict=False))
    customer = register_and_login(client, "spa@example.com")
    booking = book(client, customer, salon, spa, slots[0]).json()
    haircut = offering_id(salon, "Haircut")
    later = first_slot(client, salon, haircut, next_working_day(), asha)
    end = datetime.fromisoformat(booking["end_at"])
    start = datetime.fromisoformat(booking["start_at"])
    assert not any(start <= datetime.fromisoformat(s["start_at"]) < end for s in later)


def _concurrent(fn, n=2):
    barrier, results = threading.Barrier(n), [None] * n

    def run(i):
        barrier.wait()
        try:
            results[i] = fn(i)
        except HTTPException as error:
            results[i] = error.status_code

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_customers_same_slot_only_one_wins(client, venues, db_session):
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "General physician consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    for i in range(6):
        register_and_login(client, f"race{i}@example.com")
    from datetime import datetime

    def attempt(i):
        with TestSessionLocal() as db:
            user = db.query(User).filter_by(email=f"race{i}@example.com").one()
            booking, _ = appointments.create_booking(db, user, venue_id=venue, offering_id=offering,
                                                     provider_id=slot["provider_id"],
                                                     start_at=datetime.fromisoformat(slot["start_at"]))
            return booking.token_label

    results = _concurrent(attempt, 6)
    assert sum(isinstance(r, str) for r in results) == 1, results
    assert results.count(409) == 5
    assert db_session.query(Booking).count() == 1


def test_concurrent_bookings_get_unique_tokens(client, venues, db_session):
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "General physician consultation")
    slots = first_slot(client, venue, offering, next_working_day())[:5]
    for i in range(5):
        register_and_login(client, f"tok{i}@example.com")
    from datetime import datetime

    def attempt(i):
        with TestSessionLocal() as db:
            user = db.query(User).filter_by(email=f"tok{i}@example.com").one()
            return appointments.create_booking(db, user, venue_id=venue, offering_id=offering,
                                               provider_id=slots[i]["provider_id"],
                                               start_at=datetime.fromisoformat(slots[i]["start_at"]))[0].token_label

    tokens = _concurrent(attempt, 5)
    assert sorted(tokens) == [f"GM1-00{i}" for i in range(1, 6)], tokens
    assert db_session.query(QueueDay).one().next_token == 6


def test_exclusion_constraint_blocks_overlap_even_bypassing_service(client, venues, db_session):
    customer = register_and_login(client, "raw@example.com")
    venue, offering = venues[GREENLEAF], offering_id(venues[GREENLEAF], "General physician consultation")
    slot = first_slot(client, venue, offering, next_working_day())[0]
    created = book(client, customer, venue, offering, slot).json()
    original = db_session.query(Booking).filter_by(reference=created["reference"]).one()
    db_session.add(Booking(reference="QF-H-RAWTEST", customer_id=original.customer_id, venue_id=venue,
                           offering_id=offering, provider_id=original.provider_id, queue_day_id=original.queue_day_id,
                           start_at=original.start_at + timedelta(minutes=5),
                           end_at=original.end_at + timedelta(minutes=5), service_date=original.service_date,
                           token_number=99, token_label="X-099", status=BookingStatus.CONFIRMED))
    with pytest.raises(IntegrityError):
        db_session.commit()
