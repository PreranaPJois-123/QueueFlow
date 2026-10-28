"""Vector retrieval over pgvector with access control applied in SQL."""
from dataclasses import asdict, dataclass

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assistant import DocumentChunk, KnowledgeDocument
from app.models.models import User, UserRole
from app.rag.embeddings import get_embedder


@dataclass
class Retrieved:
    chunk_id: str
    document_id: str
    source: str
    title: str
    heading: str
    category: str
    entity_type: str | None
    entity_id: str | None
    content: str
    score: float

    def as_dict(self) -> dict:
        return asdict(self)


def access_filter(user: User):
    """Public documents for everyone; staff documents for staff/admins;
    private documents only for their owner. Enforced in the query, so another
    user's private content is never even scored."""
    clauses = [KnowledgeDocument.access_level == "public",
               and_(KnowledgeDocument.access_level == "private", KnowledgeDocument.owner_user_id == user.id)]
    if user.role in (UserRole.STAFF, UserRole.ADMIN):
        clauses.append(KnowledgeDocument.access_level == "staff")
    return or_(*clauses)


def retrieve(db: Session, query: str, user: User, k: int | None = None,
             min_score: float | None = None) -> list[Retrieved]:
    k = k or settings.RAG_TOP_K
    embedder = get_embedder()
    if min_score is None:
        min_score = settings.RAG_MIN_SCORE if settings.RAG_MIN_SCORE is not None else embedder.default_min_score
    vector = embedder.embed([query[:2000]])[0]
    distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
    rows = (db.query(DocumentChunk, KnowledgeDocument, distance)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
            .filter(DocumentChunk.embedding_model == embedder.model_id, access_filter(user))
            .order_by(distance).limit(k * 3).all())
    results: list[Retrieved] = []
    per_doc: dict[str, int] = {}
    for chunk, doc, dist in rows:
        score = 1.0 - float(dist)
        if score < min_score or per_doc.get(doc.id, 0) >= 2:  # diversity: at most 2 chunks per document
            continue
        per_doc[doc.id] = per_doc.get(doc.id, 0) + 1
        results.append(Retrieved(chunk.id, doc.id, doc.source, doc.title, chunk.heading, doc.category,
                                 doc.entity_type, doc.entity_id, chunk.content, round(score, 4)))
        if len(results) >= k:
            break
    return results


def build_context(results: list[Retrieved], max_chars: int | None = None) -> tuple[str, list[Retrieved]]:
    """Bounded context block. Document text is untrusted: angle brackets inside
    it are escaped, so a document cannot close its block or fake new ones."""
    max_chars = max_chars or settings.RAG_MAX_CONTEXT_CHARS
    used: list[Retrieved] = []
    parts: list[str] = []
    total = 0
    for index, item in enumerate(results, start=1):
        body = item.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        title = item.title.replace('"', "'").replace("<", "&lt;")
        section = item.heading.replace('"', "'").replace("<", "&lt;")
        block = f'<document id="S{index}" title="{title}" section="{section}">\n{body}\n</document>'
        if total + len(block) > max_chars and used:
            break
        parts.append(block)
        used.append(item)
        total += len(block)
    return "\n".join(parts), used
