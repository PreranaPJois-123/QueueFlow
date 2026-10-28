"""Wayzen knowledge base (pgvector) and conversation records."""
from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.models import gen_uuid


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    source = Column(String(255), nullable=False, unique=True)  # e.g. "guide:booking-hospital" or "venue:<id>"
    title = Column(String(255), nullable=False)
    category = Column(String(32), nullable=False)
    entity_type = Column(String(32), nullable=True)
    entity_id = Column(String(36), nullable=True)
    # public: any signed-in user; staff: STAFF/ADMIN only; private: owner only.
    access_level = Column(String(16), nullable=False, default="public")
    owner_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)
    embedding_model = Column(String(160), nullable=False)
    indexed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan",
                          order_by="DocumentChunk.ordinal")

    __table_args__ = (
        CheckConstraint("access_level IN ('public', 'staff', 'private')", name="ck_doc_access"),
        CheckConstraint("access_level <> 'private' OR owner_user_id IS NOT NULL", name="ck_doc_private_owner"),
        Index("ix_doc_entity", "entity_type", "entity_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False,
                         index=True)
    ordinal = Column(Integer, nullable=False)
    heading = Column(String(255), nullable=False, default="")
    content = Column(Text, nullable=False)
    # Dimension is provider-dependent, so the column is unconstrained; queries
    # always filter on embedding_model so vectors of different models never mix.
    embedding = Column(Vector(), nullable=False)
    embedding_model = Column(String(160), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    document = relationship("KnowledgeDocument", back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(120), nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan",
                            order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    mode = Column(String(16), nullable=True)   # generated | limited | error
    sources = Column(JSONB, nullable=False, default=list)
    retrieval = Column(JSONB, nullable=False, default=list)   # [{chunk_id, score}] for evaluation
    tool_calls = Column(JSONB, nullable=False, default=list)
    pending_action_id = Column(String(36), nullable=True)
    model = Column(String(160), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_role"),)


class PendingAction(Base):
    """A booking/cancellation Wayzen prepared. It only executes when the user
    presses Confirm in the UI; the model has no tool that can confirm it."""
    __tablename__ = "pending_actions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(32), nullable=False)
    arguments = Column(JSONB, nullable=False)
    summary = Column(JSONB, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    result = Column(JSONB, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'executed', 'dismissed', 'expired', 'failed')", name="ck_action_status"),
        CheckConstraint("action_type IN ('book_appointment', 'reserve_hotel', 'cancel_booking', "
                        "'cancel_reservation')", name="ck_action_type"),
    )
