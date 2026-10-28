"""Knowledge ingestion: help articles + configured venue data -> chunks -> embeddings.

Run ``python -m app.rag.ingest`` (also run on container start). Ingestion is
incremental: a document is re-embedded only when its content hash or the
embedding model changes, its version increments, and documents whose source
disappeared (deleted file, deactivated venue) are removed from the index.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.assistant import DocumentChunk, KnowledgeDocument
from app.models.venues import Offering, Provider, Specialization, Venue, VenueKind
from app.rag.chunking import chunk_markdown, normalise, parse_front_matter
from app.rag.embeddings import get_embedder

MANAGED_PREFIXES = ("guide:", "venue:", "specialization:")


@dataclass
class SourceDocument:
    source: str
    title: str
    category: str
    content: str
    access_level: str = "public"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    owner_user_id: Optional[str] = None


def knowledge_dir() -> Path:
    return Path(settings.KNOWLEDGE_DIR) if settings.KNOWLEDGE_DIR else Path(__file__).resolve().parents[2] / "knowledge"


def file_documents() -> list[SourceDocument]:
    docs = []
    for path in sorted(knowledge_dir().glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        access = meta.get("access", "public")
        if access not in ("public", "staff"):
            access = "staff"
        docs.append(SourceDocument(source=f"guide:{path.stem}", title=meta.get("title", path.stem),
                                   category=meta.get("category", "guide"), content=body, access_level=access))
    return docs


def _money(venue: Venue, amount) -> str:
    return f"{venue.currency} {amount:,.2f}"


def venue_document(venue: Venue) -> SourceDocument:
    kind = {VenueKind.HOSPITAL: "Hospital", VenueKind.SHOP: "Shop", VenueKind.HOTEL: "Hotel"}[venue.kind]
    lines = [f"# {venue.name}", "",
             f"{kind}{f' ({venue.category})' if venue.category else ''} in {venue.city}. Address: {venue.address}."]
    if venue.is_sample:
        lines.append("This is a sample (demonstration) listing, not a real partner business.")
    if venue.description:
        lines += ["", venue.description]
    if venue.kind in (VenueKind.HOSPITAL, VenueKind.SHOP):
        offerings = [o for o in venue.offerings if o.is_active]
        providers = [p for p in venue.providers if p.is_active]
        lines += ["", "## Services"]
        for o in offerings:
            spec = f" Specialization: {o.specialization.name}." if o.specialization else ""
            fee = f" Fee: {_money(venue, o.price)}." if o.price is not None else ""
            lines.append(f"- {o.name}: {o.duration_minutes} minutes.{spec}{fee} {o.description}".rstrip())
        if providers:
            lines += ["", "## Doctors" if venue.kind == VenueKind.HOSPITAL else "## Staff"]
            for p in providers:
                served = ", ".join(o.name for o in p.offerings if o.is_active) or "no services assigned"
                lines.append(f"- {p.name}{f', {p.title}' if p.title else ''}. Provides: {served}.")
        lines += ["", "## Booking policy",
                  f"Appointments can be booked up to {venue.booking_horizon_days} days ahead and at least "
                  f"{venue.min_notice_minutes} minutes in advance. Cancellation and rescheduling close "
                  f"{venue.cancel_cutoff_minutes} minutes before the appointment."]
    else:
        lines += ["", "## Room types"]
        for r in venue.room_types:
            if r.is_active:
                lines.append(f"- {r.name}: up to {r.max_occupancy} guests, {_money(venue, r.nightly_rate)} per night "
                             f"before taxes. {r.amenities}. {r.description}".rstrip())
        check_in = venue.check_in_time.strftime("%H:%M") if venue.check_in_time else "14:00"
        check_out = venue.check_out_time.strftime("%H:%M") if venue.check_out_time else "11:00"
        lines += ["", "## Hotel policies",
                  f"Check-in from {check_in}; check-out by {check_out}. Taxes: {float(venue.tax_rate) * 100:.1f}% "
                  f"of the room charge. Free cancellation until {venue.free_cancellation_hours} hours before check-in "
                  "time; later cancellations incur a charge of one night per room payable to the hotel."]
    lines += ["", "Live availability, exact prices for specific dates and queue positions come from the booking "
                  "system, not from this description."]
    return SourceDocument(source=f"venue:{venue.id}", title=venue.name, category=venue.kind.value.lower(),
                          content="\n".join(lines), entity_type="venue", entity_id=venue.id)


def specialization_documents(db: Session) -> list[SourceDocument]:
    docs = []
    for spec in db.query(Specialization).order_by(Specialization.name).all():
        hospitals = sorted({o.venue.name for o in db.query(Offering).filter(
            Offering.specialization_id == spec.id, Offering.is_active.is_(True)).all() if o.venue.is_active})
        if not hospitals:
            continue
        body = (f"# {spec.name}\n\n{spec.description}\n\nOffered on QueueFlow at: {', '.join(hospitals)}.\n\n"
                "QueueFlow helps you book a consultation; it does not give medical advice.")
        docs.append(SourceDocument(source=f"specialization:{spec.slug}", title=f"{spec.name} (specialization)",
                                   category="specialization", content=body, entity_type="specialization",
                                   entity_id=spec.id))
    return docs


def _venues(db: Session, venue_id: Optional[str] = None):
    query = db.query(Venue).options(
        selectinload(Venue.offerings).selectinload(Offering.specialization),
        selectinload(Venue.providers).selectinload(Provider.offerings), selectinload(Venue.room_types))
    if venue_id:
        query = query.filter(Venue.id == venue_id)
    return query.all()


def _hash(doc: SourceDocument) -> str:
    return hashlib.sha256("\x1f".join([doc.title, doc.category, doc.access_level, normalise(doc.content)])
                          .encode()).hexdigest()


def upsert(db: Session, doc: SourceDocument) -> str:
    embedder = get_embedder()
    digest = _hash(doc)
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.source == doc.source).first()
    if existing and existing.content_hash == digest and existing.embedding_model == embedder.model_id:
        return "unchanged"
    chunks = chunk_markdown(doc.content)
    vectors = embedder.embed([f"{doc.title}. {c.heading}. {c.content}" for c in chunks]) if chunks else []
    if existing is None:
        existing = KnowledgeDocument(source=doc.source, version=0)
        db.add(existing)
        outcome = "added"
    else:
        existing.chunks.clear()
        db.flush()
        outcome = "updated"
    existing.title, existing.category, existing.access_level = doc.title, doc.category, doc.access_level
    existing.entity_type, existing.entity_id, existing.owner_user_id = doc.entity_type, doc.entity_id, doc.owner_user_id
    existing.content_hash, existing.embedding_model = digest, embedder.model_id
    existing.version += 1
    from sqlalchemy import func
    existing.indexed_at = func.now()
    existing.chunks.extend(DocumentChunk(ordinal=c.ordinal, heading=c.heading[:255], content=c.content,
                                         embedding=v, embedding_model=embedder.model_id)
                           for c, v in zip(chunks, vectors, strict=True))
    db.flush()
    return outcome


def _remove(db: Session, sources: Iterable[str]) -> int:
    removed = 0
    for doc in db.query(KnowledgeDocument).filter(KnowledgeDocument.source.in_(list(sources))).all():
        db.delete(doc)
        removed += 1
    return removed


def ingest_all(db: Session) -> dict[str, int]:
    docs = file_documents() + [venue_document(v) for v in _venues(db) if v.is_active] + specialization_documents(db)
    counts = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0}
    for doc in docs:
        counts[upsert(db, doc)] += 1
    wanted = {d.source for d in docs}
    stale = [s for (s,) in db.query(KnowledgeDocument.source).all()
             if s.startswith(MANAGED_PREFIXES) and s not in wanted]
    counts["removed"] = _remove(db, stale)
    db.flush()
    return counts


def sync_venue_document(db: Session, venue_id: str) -> str:
    venues = _venues(db, venue_id)
    if not venues or not venues[0].is_active:
        return "removed" if _remove(db, [f"venue:{venue_id}"]) else "absent"
    return upsert(db, venue_document(venues[0]))


if __name__ == "__main__":
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        result = ingest_all(session)
        session.commit()
    print(f"Knowledge index ({get_embedder().model_id}): {result}")
