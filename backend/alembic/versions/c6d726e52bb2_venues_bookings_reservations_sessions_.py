"""venues bookings reservations sessions wayzen

Revision ID: c6d726e52bb2
Revises: 700500789b17
Create Date: 2026-10-28 15:07:37.853017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = 'c6d726e52bb2'
down_revision: Union[str, Sequence[str], None] = '700500789b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Extensions: btree_gist enables the no-overlap exclusion constraint on
    # bookings; vector (pgvector) stores Wayzen embeddings. In Docker they are
    # pre-created by the superuser init script, so this is a no-op there.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for value in ("BOOKING_CONFIRMED", "BOOKING_UPDATED", "BOOKING_CANCELLED", "SERVICE_DELAY"):
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")
    op.create_table('specializations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('slug', sa.String(length=90), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('venues',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.Enum('HOSPITAL', 'SHOP', 'HOTEL', name='venue_kind'), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('slug', sa.String(length=180), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('category', sa.String(length=64), nullable=True),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_sample', sa.Boolean(), nullable=False),
    sa.Column('booking_horizon_days', sa.Integer(), nullable=False),
    sa.Column('min_notice_minutes', sa.Integer(), nullable=False),
    sa.Column('cancel_cutoff_minutes', sa.Integer(), nullable=False),
    sa.Column('tax_rate', sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column('check_in_time', sa.Time(), nullable=True),
    sa.Column('check_out_time', sa.Time(), nullable=True),
    sa.Column('free_cancellation_hours', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('booking_horizon_days BETWEEN 1 AND 365', name='ck_venue_horizon'),
    sa.CheckConstraint('cancel_cutoff_minutes BETWEEN 0 AND 10080', name='ck_venue_cutoff'),
    sa.CheckConstraint('free_cancellation_hours BETWEEN 0 AND 720', name='ck_venue_free_cancel'),
    sa.CheckConstraint('min_notice_minutes BETWEEN 0 AND 10080', name='ck_venue_notice'),
    sa.CheckConstraint('tax_rate >= 0 AND tax_rate < 1', name='ck_venue_tax'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index('ix_venue_kind_active_city', 'venues', ['kind', 'is_active', 'city'], unique=False)
    op.create_table('audit_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=32), nullable=True),
    sa.Column('entity_id', sa.String(length=36), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_entity', 'audit_events', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_events_actor_id'), 'audit_events', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)
    op.create_table('chat_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)
    op.create_table('knowledge_documents',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('entity_type', sa.String(length=32), nullable=True),
    sa.Column('entity_id', sa.String(length=36), nullable=True),
    sa.Column('access_level', sa.String(length=16), nullable=False),
    sa.Column('owner_user_id', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('embedding_model', sa.String(length=160), nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("access_level <> 'private' OR owner_user_id IS NOT NULL", name='ck_doc_private_owner'),
    sa.CheckConstraint("access_level IN ('public', 'staff', 'private')", name='ck_doc_access'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source')
    )
    op.create_index('ix_doc_entity', 'knowledge_documents', ['entity_type', 'entity_id'], unique=False)
    op.create_table('offerings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('venue_id', sa.String(length=36), nullable=False),
    sa.Column('specialization_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('duration_minutes BETWEEN 5 AND 480', name='ck_offering_duration'),
    sa.CheckConstraint('price IS NULL OR price >= 0', name='ck_offering_price'),
    sa.ForeignKeyConstraint(['specialization_id'], ['specializations.id'], ),
    sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('venue_id', 'name', name='uq_offering_venue_name')
    )
    op.create_index('ix_offering_venue_active', 'offerings', ['venue_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_offerings_specialization_id'), 'offerings', ['specialization_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('providers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('venue_id', sa.String(length=36), nullable=False),
    sa.Column('specialization_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('bio', sa.Text(), nullable=False),
    sa.Column('token_prefix', sa.String(length=8), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("token_prefix ~ '^[A-Z0-9]{1,8}$'", name='ck_provider_prefix'),
    sa.ForeignKeyConstraint(['specialization_id'], ['specializations.id'], ),
    sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('venue_id', 'token_prefix', name='uq_provider_token_prefix')
    )
    op.create_index(op.f('ix_providers_venue_id'), 'providers', ['venue_id'], unique=False)
    op.create_table('room_types',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('venue_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('amenities', sa.String(length=500), nullable=False),
    sa.Column('max_occupancy', sa.Integer(), nullable=False),
    sa.Column('nightly_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('total_rooms', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('max_occupancy BETWEEN 1 AND 12', name='ck_room_occupancy'),
    sa.CheckConstraint('nightly_rate >= 0', name='ck_room_rate'),
    sa.CheckConstraint('total_rooms BETWEEN 0 AND 10000', name='ck_room_total'),
    sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('venue_id', 'name', name='uq_room_type_name')
    )
    op.create_index(op.f('ix_room_types_venue_id'), 'room_types', ['venue_id'], unique=False)
    op.create_table('user_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_table('venue_staff',
    sa.Column('venue_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('venue_id', 'user_id')
    )
    op.create_index(op.f('ix_venue_staff_user_id'), 'venue_staff', ['user_id'], unique=False)
    op.create_table('chat_messages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=True),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('retrieval', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tool_calls', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('pending_action_id', sa.String(length=36), nullable=True),
    sa.Column('model', sa.String(length=160), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_chat_role'),
    sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)
    op.create_table('document_chunks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('heading', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(), nullable=False),
    sa.Column('embedding_model', sa.String(length=160), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_table('pending_actions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('action_type', sa.String(length=32), nullable=False),
    sa.Column('arguments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action_type IN ('book_appointment', 'reserve_hotel', 'cancel_booking', 'cancel_reservation')", name='ck_action_type'),
    sa.CheckConstraint("status IN ('pending', 'executed', 'dismissed', 'expired', 'failed')", name='ck_action_status'),
    sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pending_actions_user_id'), 'pending_actions', ['user_id'], unique=False)
    op.create_table('provider_offerings',
    sa.Column('provider_id', sa.String(length=36), nullable=False),
    sa.Column('offering_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['offering_id'], ['offerings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('provider_id', 'offering_id')
    )
    op.create_table('queue_days',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider_id', sa.String(length=36), nullable=False),
    sa.Column('service_date', sa.Date(), nullable=False),
    sa.Column('next_token', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'PAUSED', name='queue_day_status'), nullable=False),
    sa.Column('delay_minutes', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('delay_minutes BETWEEN 0 AND 600', name='ck_queue_day_delay'),
    sa.CheckConstraint('next_token >= 1', name='ck_queue_day_token'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_id', 'service_date', name='uq_queue_day')
    )
    op.create_table('reservations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('reference', sa.String(length=16), nullable=False),
    sa.Column('customer_id', sa.String(length=36), nullable=False),
    sa.Column('venue_id', sa.String(length=36), nullable=False),
    sa.Column('room_type_id', sa.String(length=36), nullable=False),
    sa.Column('check_in', sa.Date(), nullable=False),
    sa.Column('check_out', sa.Date(), nullable=False),
    sa.Column('guests', sa.Integer(), nullable=False),
    sa.Column('rooms', sa.Integer(), nullable=False),
    sa.Column('nights', sa.Integer(), nullable=False),
    sa.Column('nightly_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('taxes', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('status', sa.Enum('CONFIRMED', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED', 'NO_SHOW', name='reservation_status'), nullable=False),
    sa.Column('cancellation_fee', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('special_requests', sa.String(length=500), nullable=True),
    sa.Column('idempotency_key', sa.String(length=64), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('check_out > check_in', name='ck_reservation_dates'),
    sa.CheckConstraint('guests >= 1', name='ck_reservation_guests'),
    sa.CheckConstraint('nights >= 1', name='ck_reservation_nights'),
    sa.CheckConstraint('rooms BETWEEN 1 AND 5', name='ck_reservation_rooms'),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['room_type_id'], ['room_types.id'], ),
    sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_id', 'idempotency_key', name='uq_reservation_idempotency'),
    sa.UniqueConstraint('reference')
    )
    op.create_index('ix_reservation_customer_checkin', 'reservations', ['customer_id', 'check_in'], unique=False)
    op.create_index('ix_reservation_venue_checkin', 'reservations', ['venue_id', 'check_in'], unique=False)
    op.create_table('room_inventory',
    sa.Column('room_type_id', sa.String(length=36), nullable=False),
    sa.Column('night', sa.Date(), nullable=False),
    sa.Column('booked', sa.Integer(), nullable=False),
    sa.CheckConstraint('booked >= 0', name='ck_inventory_booked'),
    sa.ForeignKeyConstraint(['room_type_id'], ['room_types.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('room_type_id', 'night')
    )
    op.create_table('schedules',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider_id', sa.String(length=36), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.CheckConstraint('end_time > start_time', name='ck_schedule_window'),
    sa.CheckConstraint('weekday BETWEEN 0 AND 6', name='ck_schedule_weekday'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_id', 'weekday', 'start_time', name='uq_schedule_window')
    )
    op.create_index(op.f('ix_schedules_provider_id'), 'schedules', ['provider_id'], unique=False)
    op.create_table('bookings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('reference', sa.String(length=16), nullable=False),
    sa.Column('customer_id', sa.String(length=36), nullable=False),
    sa.Column('venue_id', sa.String(length=36), nullable=False),
    sa.Column('offering_id', sa.String(length=36), nullable=False),
    sa.Column('provider_id', sa.String(length=36), nullable=False),
    sa.Column('queue_day_id', sa.String(length=36), nullable=False),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('service_date', sa.Date(), nullable=False),
    sa.Column('token_number', sa.Integer(), nullable=False),
    sa.Column('token_label', sa.String(length=16), nullable=False),
    sa.Column('status', sa.Enum('CONFIRMED', 'CHECKED_IN', 'IN_SERVICE', 'COMPLETED', 'CANCELLED', 'NO_SHOW', name='booking_status'), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('idempotency_key', sa.String(length=64), nullable=True),
    sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('provider_id'), '='), (sa.text("tstzrange(start_at, end_at, '[)')"), '&&'), where=sa.text("status IN ('CONFIRMED', 'CHECKED_IN', 'IN_SERVICE')"), using='gist', name='ex_booking_provider_overlap'),
    sa.CheckConstraint('end_at > start_at', name='ck_booking_window'),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['offering_id'], ['offerings.id'], ),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
    sa.ForeignKeyConstraint(['queue_day_id'], ['queue_days.id'], ),
    sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_id', 'idempotency_key', name='uq_booking_idempotency'),
    sa.UniqueConstraint('queue_day_id', 'token_number', name='uq_booking_token'),
    sa.UniqueConstraint('reference')
    )
    op.create_index('ix_booking_customer_start', 'bookings', ['customer_id', 'start_at'], unique=False)
    op.create_index('ix_booking_queue_day_status', 'bookings', ['queue_day_id', 'status'], unique=False)
    op.create_index('ix_booking_venue_date', 'bookings', ['venue_id', 'service_date'], unique=False)
    op.add_column('notifications', sa.Column('booking_id', sa.String(length=36), nullable=True))
    op.add_column('notifications', sa.Column('reservation_id', sa.String(length=36), nullable=True))
    op.add_column('notifications', sa.Column('dedupe_key', sa.String(length=160), nullable=True))
    op.create_index(op.f('ix_notifications_booking_id'), 'notifications', ['booking_id'], unique=False)
    op.create_unique_constraint('uq_notifications_dedupe_key', 'notifications', ['dedupe_key'])
    op.create_foreign_key('fk_notifications_reservation', 'notifications', 'reservations', ['reservation_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_notifications_booking', 'notifications', 'bookings', ['booking_id'], ['id'], ondelete='SET NULL')
    op.add_column('users', sa.Column('pref_sound_enabled', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('pref_browser_enabled', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'pref_browser_enabled')
    op.drop_column('users', 'pref_sound_enabled')
    op.drop_constraint('fk_notifications_booking', 'notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_reservation', 'notifications', type_='foreignkey')
    op.drop_constraint('uq_notifications_dedupe_key', 'notifications', type_='unique')
    op.drop_index(op.f('ix_notifications_booking_id'), table_name='notifications')
    op.drop_column('notifications', 'dedupe_key')
    op.drop_column('notifications', 'reservation_id')
    op.drop_column('notifications', 'booking_id')
    op.drop_index('ix_booking_venue_date', table_name='bookings')
    op.drop_index('ix_booking_queue_day_status', table_name='bookings')
    op.drop_index('ix_booking_customer_start', table_name='bookings')
    op.drop_table('bookings')
    op.drop_index(op.f('ix_schedules_provider_id'), table_name='schedules')
    op.drop_table('schedules')
    op.drop_table('room_inventory')
    op.drop_index('ix_reservation_venue_checkin', table_name='reservations')
    op.drop_index('ix_reservation_customer_checkin', table_name='reservations')
    op.drop_table('reservations')
    op.drop_table('queue_days')
    op.drop_table('provider_offerings')
    op.drop_index(op.f('ix_pending_actions_user_id'), table_name='pending_actions')
    op.drop_table('pending_actions')
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index(op.f('ix_chat_messages_session_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_venue_staff_user_id'), table_name='venue_staff')
    op.drop_table('venue_staff')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index(op.f('ix_room_types_venue_id'), table_name='room_types')
    op.drop_table('room_types')
    op.drop_index(op.f('ix_providers_venue_id'), table_name='providers')
    op.drop_table('providers')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_offerings_specialization_id'), table_name='offerings')
    op.drop_index('ix_offering_venue_active', table_name='offerings')
    op.drop_table('offerings')
    op.drop_index('ix_doc_entity', table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
    op.drop_index(op.f('ix_chat_sessions_user_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
    op.drop_index(op.f('ix_audit_events_created_at'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_actor_id'), table_name='audit_events')
    op.drop_index('ix_audit_entity', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index('ix_venue_kind_active_city', table_name='venues')
    op.drop_table('venues')
    op.drop_table('specializations')
    for enum_name in ("booking_status", "reservation_status", "queue_day_status", "venue_kind"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    # notification_type keeps its added values: PostgreSQL cannot drop enum values.
    # ### end Alembic commands ###
