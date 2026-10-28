"""Idempotent development / demonstration seed data.

    python -m app.seed                       # sample venues, services, doctors, rooms
    python -m app.seed --assign-staff EMAIL  # also assign an existing STAFF account to every sample venue

Every venue created here has ``is_sample = True`` and is labelled "Sample" in
the UI. They are fictional businesses; no real hospital, shop or hotel is
represented. Existing venues (matched by slug) are never modified, so
administrator edits survive re-seeding. No user accounts are created.
"""
import argparse
from datetime import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import User, UserRole
from app.models.venues import (
    Offering, Provider, ProviderOffering, RoomType, Schedule, Specialization, Venue, VenueKind, VenueStaff,
)

SPECIALIZATIONS = {
    "General Medicine": "Consultations for common illnesses, check-ups and referrals to specialists.",
    "Cardiology": "Heart and blood-vessel care: consultations, ECG review and follow-up of heart conditions.",
    "Dermatology": "Skin, hair and nail conditions.",
    "Orthopedics": "Bones, joints, ligaments and sports injuries.",
    "Pediatrics": "Medical care for infants, children and adolescents.",
    "ENT": "Ear, nose and throat care.",
    "Ophthalmology": "Eye examinations and eye-condition consultations.",
    "Neurology": "Brain, spinal cord and nerve conditions.",
}

WEEKDAYS = range(0, 6)  # Monday-Saturday
MORNING, AFTERNOON = (time(9, 0), time(13, 0)), (time(14, 0), time(17, 0))

HOSPITALS = [
    {"name": "Greenleaf Multispeciality Hospital", "city": "Bengaluru", "address": "12 Lakeview Road, Jayanagar",
     "phone": "+91 80 0000 1001",
     "description": "A sample multispeciality hospital with outpatient consultations across eight specialities.",
     "services": [("General Medicine", "General physician consultation", 15, "500"),
                  ("Cardiology", "Cardiology consultation", 20, "900"),
                  ("Dermatology", "Dermatology consultation", 15, "700"),
                  ("Orthopedics", "Orthopedic consultation", 20, "800"),
                  ("ENT", "ENT consultation", 15, "600"),
                  ("Neurology", "Neurology consultation", 30, "1200")],
     "doctors": [("Dr. Ananya Rao", "Consultant Physician", "General Medicine", "GM1", ["General physician consultation"]),
                 ("Dr. Vikram Shetty", "Senior Cardiologist", "Cardiology", "CAR1", ["Cardiology consultation"]),
                 ("Dr. Meera Iyer", "Cardiologist", "Cardiology", "CAR2", ["Cardiology consultation"]),
                 ("Dr. Farah Khan", "Dermatologist", "Dermatology", "DRM1", ["Dermatology consultation"]),
                 ("Dr. Rohan Kulkarni", "Orthopedic Surgeon", "Orthopedics", "ORT1", ["Orthopedic consultation"]),
                 ("Dr. Lakshmi Menon", "ENT Specialist", "ENT", "ENT1", ["ENT consultation"]),
                 ("Dr. Arjun Nair", "Neurologist", "Neurology", "NEU1", ["Neurology consultation"])]},
    {"name": "Lotus Children & Family Clinic", "city": "Bengaluru", "address": "45 Temple Street, Malleshwaram",
     "phone": "+91 80 0000 1002",
     "description": "A sample family clinic focused on children's health, general medicine and eye care.",
     "services": [("Pediatrics", "Pediatric consultation", 15, "600"),
                  ("General Medicine", "Family medicine consultation", 15, "450"),
                  ("Ophthalmology", "Eye examination", 20, "650")],
     "doctors": [("Dr. Kavya Hegde", "Pediatrician", "Pediatrics", "PED1", ["Pediatric consultation"]),
                 ("Dr. Sameer Joshi", "Family Physician", "General Medicine", "FM1", ["Family medicine consultation"]),
                 ("Dr. Neha Bhat", "Ophthalmologist", "Ophthalmology", "EYE1", ["Eye examination"])]},
    {"name": "Riverside General Hospital", "city": "Mysuru", "address": "8 Riverside Avenue, Saraswathipuram",
     "phone": "+91 821 000 1003",
     "description": "A sample general hospital in Mysuru with dermatology, orthopedics and general medicine clinics.",
     "services": [("General Medicine", "General physician consultation", 15, "400"),
                  ("Dermatology", "Skin clinic consultation", 15, "550"),
                  ("Orthopedics", "Joint and bone clinic", 20, "700")],
     "doctors": [("Dr. Prakash Gowda", "Physician", "General Medicine", "GM1", ["General physician consultation"]),
                 ("Dr. Shalini Murthy", "Dermatologist", "Dermatology", "DRM1", ["Skin clinic consultation"]),
                 ("Dr. Imran Sheikh", "Orthopedist", "Orthopedics", "ORT1", ["Joint and bone clinic"])]},
]

SHOPS = [
    {"name": "Bloom Unisex Salon", "city": "Bengaluru", "category": "Salon", "address": "22 Brigade Lane",
     "description": "A sample salon offering haircuts, styling and grooming.",
     "services": [("Haircut", 30, "350"), ("Hair spa", 45, "900"), ("Beard trim", 15, "150")],
     "staff": [("Asha", "Senior Stylist", "AS", ["Haircut", "Hair spa"]),
               ("Ravi", "Stylist", "RV", ["Haircut", "Beard trim"])]},
    {"name": "FixPoint Phone & Laptop Repair", "city": "Bengaluru", "category": "Repair shop",
     "address": "5 Market Road, Indiranagar",
     "description": "A sample repair desk for phones and laptops. Diagnosis appointments only; repair time varies.",
     "services": [("Phone diagnosis", 20, "199"), ("Laptop diagnosis", 30, "299"),
                  ("Screen replacement drop-off", 15, None)],
     "staff": [("Karthik", "Repair Technician", "KT", ["Phone diagnosis", "Screen replacement drop-off"]),
               ("Divya", "Laptop Technician", "DV", ["Laptop diagnosis"])]},
    {"name": "ClearPath Tax & Finance Desk", "city": "Mysuru", "category": "Consultation",
     "address": "17 Sayyaji Rao Road",
     "description": "A sample consultation desk for tax filing help and document review.",
     "services": [("Tax filing consultation", 30, "500"), ("Document review", 20, "300")],
     "staff": [("Suresh", "Tax Consultant", "SU", ["Tax filing consultation", "Document review"])]},
]

HOTELS = [
    {"name": "Palm Courtyard Hotel", "city": "Bengaluru", "address": "90 MG Road",
     "description": "A sample business hotel near the city centre with an on-site restaurant.",
     "tax_rate": "0.12", "free_cancellation_hours": 24, "check_in": time(14, 0), "check_out": time(11, 0),
     "rooms": [("Standard Queen", "Queen bed, work desk, city view.", "Wi-Fi, air conditioning, breakfast", 2, "3200", 10),
               ("Deluxe Twin", "Two single beds and a seating area.", "Wi-Fi, air conditioning, breakfast", 2, "4100", 6),
               ("Family Suite", "Separate bedroom and living room.", "Wi-Fi, kitchenette, breakfast", 4, "6800", 2)]},
    {"name": "Hilltop Residency", "city": "Mysuru", "address": "3 Chamundi Hill Road",
     "description": "A sample heritage-style guesthouse with garden views.",
     "tax_rate": "0.12", "free_cancellation_hours": 48, "check_in": time(13, 0), "check_out": time(10, 0),
     "rooms": [("Garden Room", "Double bed overlooking the garden.", "Wi-Fi, breakfast", 2, "2600", 5),
               ("Heritage Suite", "Spacious suite with period furniture.", "Wi-Fi, breakfast, balcony", 3, "5200", 1)]},
]


def _slug(name: str, city: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", f"{name} {city}".lower()).strip("-")


def _schedules(provider: Provider) -> None:
    for day in WEEKDAYS:
        for start, end in (MORNING, AFTERNOON):
            provider.schedules.append(Schedule(weekday=day, start_time=start, end_time=end))


def seed(db: Session) -> dict:
    created = {"specializations": 0, "venues": 0}
    specs = {s.name: s for s in db.query(Specialization).all()}
    for name, description in SPECIALIZATIONS.items():
        if name not in specs:
            specs[name] = Specialization(name=name, slug=_slug(name, "").strip("-"), description=description)
            db.add(specs[name])
            created["specializations"] += 1
    db.flush()

    def new_venue(data: dict, kind: VenueKind, **extra) -> Venue | None:
        slug = _slug(data["name"], data["city"])
        if db.query(Venue.id).filter(Venue.slug == slug).first():
            return None
        venue = Venue(kind=kind, name=data["name"], slug=slug, city=data["city"], address=data["address"],
                      description=data["description"], phone=data.get("phone"), category=data.get("category"),
                      timezone="Asia/Kolkata", currency="INR", is_sample=True, is_active=True, **extra)
        db.add(venue)
        db.flush()
        created["venues"] += 1
        return venue

    for data in HOSPITALS:
        venue = new_venue(data, VenueKind.HOSPITAL, cancel_cutoff_minutes=120, min_notice_minutes=30,
                          booking_horizon_days=30)
        if venue is None:
            continue
        offerings = {}
        for spec, name, minutes, fee in data["services"]:
            offerings[name] = Offering(venue_id=venue.id, specialization_id=specs[spec].id, name=name,
                                       description=SPECIALIZATIONS[spec], duration_minutes=minutes,
                                       price=Decimal(fee))
            db.add(offerings[name])
        db.flush()
        for name, title, spec, prefix, services in data["doctors"]:
            doctor = Provider(venue_id=venue.id, specialization_id=specs[spec].id, name=name, title=title,
                              token_prefix=prefix, bio=f"{title} at {venue.name} (sample profile).")
            _schedules(doctor)
            db.add(doctor)
            db.flush()
            db.add_all(ProviderOffering(provider_id=doctor.id, offering_id=offerings[s].id) for s in services)

    for data in SHOPS:
        venue = new_venue(data, VenueKind.SHOP, cancel_cutoff_minutes=60, min_notice_minutes=15,
                          booking_horizon_days=21)
        if venue is None:
            continue
        offerings = {}
        for name, minutes, fee in data["services"]:
            offerings[name] = Offering(venue_id=venue.id, name=name, duration_minutes=minutes,
                                       price=Decimal(fee) if fee else None,
                                       description=f"{name} at {venue.name}.")
            db.add(offerings[name])
        db.flush()
        for name, title, prefix, services in data["staff"]:
            member = Provider(venue_id=venue.id, name=name, title=title, token_prefix=prefix,
                              bio=f"{title} (sample profile).")
            _schedules(member)
            db.add(member)
            db.flush()
            db.add_all(ProviderOffering(provider_id=member.id, offering_id=offerings[s].id) for s in services)

    for data in HOTELS:
        venue = new_venue(data, VenueKind.HOTEL, tax_rate=Decimal(data["tax_rate"]),
                          free_cancellation_hours=data["free_cancellation_hours"], check_in_time=data["check_in"],
                          check_out_time=data["check_out"])
        if venue is None:
            continue
        for name, description, amenities, occupancy, rate, total in data["rooms"]:
            db.add(RoomType(venue_id=venue.id, name=name, description=description, amenities=amenities,
                            max_occupancy=occupancy, nightly_rate=Decimal(rate), total_rooms=total))
    db.flush()
    return created


def assign_staff(db: Session, email: str) -> int:
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None or user.role not in (UserRole.STAFF, UserRole.ADMIN):
        raise SystemExit(f"{email} must be an existing STAFF or ADMIN account")
    count = 0
    for venue in db.query(Venue).filter(Venue.is_sample.is_(True)).all():
        if not db.get(VenueStaff, (venue.id, user.id)):
            db.add(VenueStaff(venue_id=venue.id, user_id=user.id))
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--assign-staff", metavar="EMAIL")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = seed(session)
        if args.assign_staff:
            result["staff_assignments"] = assign_staff(session, args.assign_staff)
        session.commit()
    print(f"Seed complete: {result}")
