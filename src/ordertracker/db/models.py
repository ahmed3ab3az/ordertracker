"""SQLAlchemy ORM models for OrderTracker.

The schema mirrors the deliverable spec:

* ``users``                — login accounts (Admin / Partner)
* ``partners``             — partner profile linked to a user
* ``production_companies`` — upstream order sources (PC)
* ``importing_companies``  — downstream delivery providers (IC)
* ``orders``               — the lifecycle entity
* ``days``                 — daily open/closed state
* ``daily_partner_shares`` — capital contributed per partner per day (input)
* ``daily_ic_snapshots``   — immutable per-day-per-IC profit snapshot
* ``daily_partner_snapshots`` — immutable per-day-per-partner profit snapshot
* ``audit_logs``           — append-only action log
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..constants import (
    AuditAction,
    DayState,
    EntityType,
    OrderStatus,
    UserRole,
)
from .base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Lockout tracking
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    partner: Mapped[Partner | None] = relationship(back_populates="user", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role.value})>"


# ---------------------------------------------------------------------------
# Partners
# ---------------------------------------------------------------------------
class Partner(Base):
    __tablename__ = "partners"

    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="partner")
    shares: Mapped[list[DailyPartnerShare]] = relationship(back_populates="partner")
    snapshots: Mapped[list[DailyPartnerSnapshot]] = relationship(back_populates="partner")


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
class ProductionCompany(Base):
    __tablename__ = "production_companies"

    pc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orders: Mapped[list[Order]] = relationship(back_populates="production_company")

    __table_args__ = (
        CheckConstraint("shipping_cost >= 0", name="shipping_cost_nonneg"),
    )


class ImportingCompany(Base):
    __tablename__ = "importing_companies"

    ic_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    profit_per_order: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    day_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orders: Mapped[list[Order]] = relationship(back_populates="importing_company")
    snapshots: Mapped[list[DailyICSnapshot]] = relationship(back_populates="importing_company")

    __table_args__ = (
        CheckConstraint("profit_per_order >= 0", name="profit_per_order_nonneg"),
        CheckConstraint("day_cost >= 0", name="day_cost_nonneg"),
    )


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    order_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.NEW
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    production_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_companies.pc_id", ondelete="RESTRICT"), nullable=False
    )
    importing_company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("importing_companies.ic_id", ondelete="RESTRICT"), nullable=True
    )

    print_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    production_company: Mapped[ProductionCompany] = relationship(back_populates="orders")
    importing_company: Mapped[ImportingCompany | None] = relationship(back_populates="orders")

    __table_args__ = (
        CheckConstraint("price >= 0", name="price_nonneg"),
        CheckConstraint("print_count >= 0", name="print_count_nonneg"),
        Index("ix_orders_date_status", "date", "status"),
        Index("ix_orders_date_ic", "date", "importing_company_id"),
        Index("ix_orders_date_pc", "date", "production_company_id"),
    )


# ---------------------------------------------------------------------------
# Days
# ---------------------------------------------------------------------------
class Day(Base):
    __tablename__ = "days"

    day_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    state: Mapped[DayState] = mapped_column(
        SAEnum(DayState, name="day_state"), nullable=False, default=DayState.OPEN
    )

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Daily partner share (input)
# ---------------------------------------------------------------------------
class DailyPartnerShare(Base):
    __tablename__ = "daily_partner_shares"

    share_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.partner_id", ondelete="RESTRICT"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    daily_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    partner: Mapped[Partner] = relationship(back_populates="shares")

    __table_args__ = (
        UniqueConstraint("partner_id", "date", name="uq_partner_date"),
        CheckConstraint("daily_share >= 0", name="daily_share_nonneg"),
    )


# ---------------------------------------------------------------------------
# Snapshots — immutable, append-only
# ---------------------------------------------------------------------------
class DailyICSnapshot(Base):
    __tablename__ = "daily_ic_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("importing_companies.ic_id", ondelete="RESTRICT"), nullable=False
    )
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    day_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    num_delivered: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    importing_company: Mapped[ImportingCompany] = relationship(back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint("date", "ic_id", name="uq_ic_snapshot_date"),
    )


class DailyPartnerSnapshot(Base):
    __tablename__ = "daily_partner_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.partner_id", ondelete="RESTRICT"), nullable=False
    )
    ic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("importing_companies.ic_id", ondelete="RESTRICT"), nullable=False
    )
    daily_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    partner_pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    final_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    partner: Mapped[Partner] = relationship(back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint("date", "partner_id", "ic_id", name="uq_partner_snapshot_date_ic"),
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, name="entity_type"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction, name="audit_action"), nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )
