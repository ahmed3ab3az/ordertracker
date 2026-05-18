"""Company services — production + importing companies, with soft-delete safety."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import AuditAction, EntityType, OrderStatus
from ..db.models import ImportingCompany, Order, ProductionCompany
from .audit import write_audit


@dataclass
class CompanyDailyStats:
    num_orders: int
    num_delivered: int
    num_returned: int
    num_postponed: int
    num_on_hold: int

    def assert_balanced(self) -> None:
        total = self.num_delivered + self.num_returned + self.num_postponed + self.num_on_hold
        if total != self.num_orders:
            raise AssertionError(
                f"Stats out of balance: orders={self.num_orders} sum={total}"
            )


T = TypeVar("T")


class _Repo(Generic[T]):
    model: type[T]
    pk_attr: str
    entity_type: EntityType

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_active(self) -> list[T]:
        return list(
            self.session.execute(
                select(self.model).where(self.model.is_deleted.is_(False)).order_by(self.model.name)  # type: ignore[attr-defined]
            ).scalars()
        )

    def soft_delete(self, *, pk: int, actor_user_id) -> None:
        obj = self.session.get(self.model, pk)
        if obj is None:
            raise ValueError(f"{self.model.__name__} not found.")
        # Ensure no orders reference it.
        order_count = self.session.execute(
            select(func.count(Order.order_id)).where(
                getattr(Order, _fk_for(self.model)) == pk
            )
        ).scalar_one()
        if order_count:
            raise ValueError(
                f"Cannot delete {self.model.__name__} — {order_count} orders still reference it."
            )
        if obj.is_deleted:  # type: ignore[attr-defined]
            return
        obj.is_deleted = True  # type: ignore[attr-defined]
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=self.entity_type,
            entity_id=getattr(obj, self.pk_attr),
            action=AuditAction.DELETE,
            new={"is_deleted": True},
        )
        self.session.commit()


def _fk_for(model: type) -> str:
    if model is ProductionCompany:
        return "production_company_id"
    if model is ImportingCompany:
        return "importing_company_id"
    raise TypeError(f"No FK mapping for {model}.")


# ---------------------------------------------------------------------------
# Production Company
# ---------------------------------------------------------------------------
class ProductionCompanyService(_Repo[ProductionCompany]):
    model = ProductionCompany
    pk_attr = "pc_id"
    entity_type = EntityType.PRODUCTION_COMPANY

    def create(self, *, name: str, shipping_cost: Decimal, actor_user_id) -> ProductionCompany:
        pc = ProductionCompany(name=name.strip(), shipping_cost=shipping_cost)
        self.session.add(pc)
        self.session.flush()
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=self.entity_type,
            entity_id=pc.pc_id,
            action=AuditAction.CREATE,
            new={"name": pc.name, "shipping_cost": str(pc.shipping_cost)},
        )
        self.session.commit()
        return pc

    def update(
        self, *, pc_id: int, name: str | None = None, shipping_cost: Decimal | None = None, actor_user_id
    ) -> ProductionCompany:
        pc = self.session.get(ProductionCompany, pc_id)
        if pc is None or pc.is_deleted:
            raise ValueError("Production company not found.")
        before = {"name": pc.name, "shipping_cost": str(pc.shipping_cost)}
        if name is not None:
            pc.name = name.strip()
        if shipping_cost is not None:
            pc.shipping_cost = shipping_cost
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=self.entity_type,
            entity_id=pc.pc_id,
            action=AuditAction.UPDATE,
            old=before,
            new={"name": pc.name, "shipping_cost": str(pc.shipping_cost)},
        )
        self.session.commit()
        return pc

    def daily_stats(self, *, pc_id: int, on_date: date) -> CompanyDailyStats:
        return _company_daily_stats(self.session, pc_id=pc_id, on_date=on_date, by="pc")


# ---------------------------------------------------------------------------
# Importing Company
# ---------------------------------------------------------------------------
class ImportingCompanyService(_Repo[ImportingCompany]):
    model = ImportingCompany
    pk_attr = "ic_id"
    entity_type = EntityType.IMPORTING_COMPANY

    def create(
        self,
        *,
        name: str,
        profit_per_order: Decimal,
        day_cost: Decimal,
        actor_user_id,
    ) -> ImportingCompany:
        ic = ImportingCompany(name=name.strip(), profit_per_order=profit_per_order, day_cost=day_cost)
        self.session.add(ic)
        self.session.flush()
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=self.entity_type,
            entity_id=ic.ic_id,
            action=AuditAction.CREATE,
            new={
                "name": ic.name,
                "profit_per_order": str(ic.profit_per_order),
                "day_cost": str(ic.day_cost),
            },
        )
        self.session.commit()
        return ic

    def update(
        self,
        *,
        ic_id: int,
        name: str | None = None,
        profit_per_order: Decimal | None = None,
        day_cost: Decimal | None = None,
        actor_user_id,
    ) -> ImportingCompany:
        ic = self.session.get(ImportingCompany, ic_id)
        if ic is None or ic.is_deleted:
            raise ValueError("Importing company not found.")
        before = {
            "name": ic.name,
            "profit_per_order": str(ic.profit_per_order),
            "day_cost": str(ic.day_cost),
        }
        if name is not None:
            ic.name = name.strip()
        if profit_per_order is not None:
            ic.profit_per_order = profit_per_order
        if day_cost is not None:
            ic.day_cost = day_cost
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=self.entity_type,
            entity_id=ic.ic_id,
            action=AuditAction.UPDATE,
            old=before,
            new={
                "name": ic.name,
                "profit_per_order": str(ic.profit_per_order),
                "day_cost": str(ic.day_cost),
            },
        )
        self.session.commit()
        return ic

    def daily_stats(self, *, ic_id: int, on_date: date) -> CompanyDailyStats:
        return _company_daily_stats(self.session, pc_id=ic_id, on_date=on_date, by="ic")


# ---------------------------------------------------------------------------
# Shared stats query
# ---------------------------------------------------------------------------
def _company_daily_stats(
    session: Session, *, pc_id: int, on_date: date, by: str
) -> CompanyDailyStats:
    fk = Order.production_company_id if by == "pc" else Order.importing_company_id

    base = select(Order).where(
        Order.date == on_date,
        Order.is_deleted.is_(False),
        fk == pc_id,
    )

    def count_with(status: OrderStatus) -> int:
        q = select(func.count()).select_from(base.where(Order.status == status).subquery())
        return int(session.execute(q).scalar_one())

    delivered = count_with(OrderStatus.DELIVERED)
    returned = count_with(OrderStatus.RETURNED)
    postponed = count_with(OrderStatus.POSTPONED)
    on_hold = count_with(OrderStatus.ON_HOLD)
    new_count = count_with(OrderStatus.NEW)
    # Per spec, NEW orders shouldn't appear here but if they do, count them as ON_HOLD-equivalent.
    on_hold += new_count

    total_q = select(func.count()).select_from(base.subquery())
    total = int(session.execute(total_q).scalar_one())

    stats = CompanyDailyStats(
        num_orders=total,
        num_delivered=delivered,
        num_returned=returned,
        num_postponed=postponed,
        num_on_hold=on_hold,
    )
    stats.assert_balanced()
    return stats
