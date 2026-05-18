"""Order lifecycle service.

Handles:
* Bulk creation from Excel imports.
* Status transitions guarded by ``constants.ALLOWED_TRANSITIONS_*``.
* Optimistic concurrency control via ``updated_at``.
* IC assignment moving ``NEW`` → ``ON_HOLD``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import (
    ALLOWED_TRANSITIONS_CLOSED_DAY,
    ALLOWED_TRANSITIONS_OPEN_DAY,
    AuditAction,
    DayState,
    EntityType,
    OrderStatus,
)
from ..db.models import Day, Order, ProductionCompany
from .audit import write_audit
from .order_key import build_order_key, next_daily_seq


class ConcurrentEditError(Exception):
    """Raised when optimistic locking detects a stale ``updated_at``."""


class DayLockedError(Exception):
    """Raised when an action targets a closed day where it is no longer allowed."""


class InvalidTransitionError(Exception):
    """Raised when a status change isn't permitted by the state machine."""


@dataclass
class OrderImportInput:
    name: str
    address: str
    price: Decimal


def _day_state(session: Session, on_date: date) -> DayState:
    day = session.execute(select(Day).where(Day.date == on_date)).scalar_one_or_none()
    if day is None:
        return DayState.OPEN
    return day.state


def _is_day_open(state: DayState) -> bool:
    return state in (DayState.OPEN, DayState.REOPENED)


class OrderService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ CREATE
    def import_bulk(
        self,
        *,
        rows: list[OrderImportInput],
        production_company_id: int,
        on_date: date,
        actor_user_id: uuid.UUID,
    ) -> list[Order]:
        """Create N orders atomically. Returns the persisted instances."""
        if not rows:
            return []
        state = _day_state(self.session, on_date)
        if not _is_day_open(state):
            raise DayLockedError("Cannot import into a closed day.")

        pc = self.session.get(ProductionCompany, production_company_id)
        if pc is None or pc.is_deleted:
            raise ValueError("Production company not found.")

        start_seq = next_daily_seq(self.session, on_date)
        created: list[Order] = []
        for i, row in enumerate(rows):
            order = Order(
                order_key=build_order_key(pc_id=pc.pc_id, on_date=on_date, seq=start_seq + i),
                name=row.name.strip(),
                address=row.address.strip(),
                price=row.price,
                status=OrderStatus.NEW,
                date=on_date,
                production_company_id=pc.pc_id,
            )
            self.session.add(order)
            created.append(order)
        self.session.flush()

        for order in created:
            write_audit(
                self.session,
                user_id=actor_user_id,
                entity_type=EntityType.ORDER,
                entity_id=order.order_id,
                action=AuditAction.CREATE,
                new={
                    "order_key": order.order_key,
                    "name": order.name,
                    "price": str(order.price),
                    "pc_id": order.production_company_id,
                    "status": order.status.value,
                },
            )
        self.session.commit()
        return created

    # ------------------------------------------------------------------ ASSIGN
    def assign_ic(
        self,
        *,
        order_id: uuid.UUID,
        ic_id: int,
        expected_updated_at: datetime,
        actor_user_id: uuid.UUID,
    ) -> Order:
        order = self._load_for_update(order_id, expected_updated_at)
        if order.status is not OrderStatus.NEW:
            raise InvalidTransitionError("IC can only be assigned to orders in NEW status.")
        state = _day_state(self.session, order.date)
        if not _is_day_open(state):
            raise DayLockedError("Cannot assign IC on a closed day.")
        before = {"importing_company_id": order.importing_company_id, "status": order.status.value}
        order.importing_company_id = ic_id
        order.status = OrderStatus.ON_HOLD
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.ORDER,
            entity_id=order.order_id,
            action=AuditAction.UPDATE,
            old=before,
            new={"importing_company_id": ic_id, "status": order.status.value},
        )
        self.session.commit()
        return order

    # --------------------------------------------------------------- TRANSITION
    def transition(
        self,
        *,
        order_id: uuid.UUID,
        new_status: OrderStatus,
        expected_updated_at: datetime,
        actor_user_id: uuid.UUID,
    ) -> Order:
        order = self._load_for_update(order_id, expected_updated_at)
        state = _day_state(self.session, order.date)
        allowed = (
            ALLOWED_TRANSITIONS_OPEN_DAY if _is_day_open(state) else ALLOWED_TRANSITIONS_CLOSED_DAY
        )
        targets = allowed.get(order.status, set())
        if new_status not in targets:
            raise InvalidTransitionError(
                f"Cannot move from {order.status.value} to {new_status.value} "
                f"on a {'closed' if not _is_day_open(state) else 'open'} day."
            )
        before = {"status": order.status.value}
        order.status = new_status
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.ORDER,
            entity_id=order.order_id,
            action=AuditAction.UPDATE,
            old=before,
            new={"status": new_status.value},
        )
        self.session.commit()
        return order

    # ----------------------------------------------------------------- LOOKUP
    def by_key(self, order_key: str) -> Order | None:
        return self.session.execute(
            select(Order).where(Order.order_key == order_key, Order.is_deleted.is_(False))
        ).scalar_one_or_none()

    def list_for_date(self, *, on_date: date) -> list[Order]:
        return list(
            self.session.execute(
                select(Order)
                .where(Order.date == on_date, Order.is_deleted.is_(False))
                .order_by(Order.order_key)
            ).scalars()
        )

    # ----------------------------------------------------------------- HELPER
    def _load_for_update(self, order_id: uuid.UUID, expected_updated_at: datetime) -> Order:
        order = self.session.get(Order, order_id)
        if order is None or order.is_deleted:
            raise ValueError("Order not found.")
        if order.updated_at != expected_updated_at:
            raise ConcurrentEditError(
                "Order was modified by another user. Please refresh and retry."
            )
        return order
