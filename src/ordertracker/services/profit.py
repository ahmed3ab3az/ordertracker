"""Profit calculation — pure functions for live-view math.

Snapshot persistence lives in :mod:`services.days`. This module is only
about turning raw inputs into the numbers shown on the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import OrderStatus
from ..db.models import (
    DailyPartnerShare,
    ImportingCompany,
    Order,
    Partner,
)

_CENT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass
class ICProfitLine:
    ic_id: int
    ic_name: str
    profit_per_order: Decimal
    num_delivered: int
    gross_profit: Decimal
    day_cost: Decimal
    net_profit: Decimal


@dataclass
class PartnerProfitLine:
    partner_id: str
    partner_name: str
    daily_share: Decimal
    partner_pct: Decimal
    final_profit: Decimal


@dataclass
class DailyProfitView:
    on_date: date
    total_capital: Decimal
    ic_lines: list[ICProfitLine]
    partner_lines: list[PartnerProfitLine]
    total_net_profit: Decimal


def compute_daily_profit(session: Session, *, on_date: date) -> DailyProfitView:
    # --- per-IC numbers
    ic_lines: list[ICProfitLine] = []
    for ic in session.execute(
        select(ImportingCompany).where(ImportingCompany.is_deleted.is_(False))
    ).scalars():
        delivered = session.execute(
            select(func.count(Order.order_id)).where(
                Order.date == on_date,
                Order.importing_company_id == ic.ic_id,
                Order.status == OrderStatus.DELIVERED,
                Order.is_deleted.is_(False),
            )
        ).scalar_one()
        gross = _q(Decimal(delivered) * ic.profit_per_order)
        net = _q(gross - ic.day_cost) if delivered else _q(Decimal("0"))
        ic_lines.append(
            ICProfitLine(
                ic_id=ic.ic_id,
                ic_name=ic.name,
                profit_per_order=ic.profit_per_order,
                num_delivered=int(delivered),
                gross_profit=gross,
                day_cost=ic.day_cost if delivered else Decimal("0.00"),
                net_profit=net,
            )
        )

    total_net = _q(sum((line.net_profit for line in ic_lines), start=Decimal("0.00")))

    # --- partner allocations
    shares = list(
        session.execute(
            select(DailyPartnerShare, Partner)
            .join(Partner, Partner.partner_id == DailyPartnerShare.partner_id)
            .where(DailyPartnerShare.date == on_date, Partner.is_deleted.is_(False))
        )
    )
    total_capital = _q(sum((s.daily_share for s, _ in shares), start=Decimal("0.00")))

    partner_lines: list[PartnerProfitLine] = []
    if total_capital > 0 and total_net != 0:
        for share, partner in shares:
            pct = (share.daily_share / total_capital).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            final = _q(total_net * pct)
            partner_lines.append(
                PartnerProfitLine(
                    partner_id=str(partner.partner_id),
                    partner_name=partner.name,
                    daily_share=share.daily_share,
                    partner_pct=pct,
                    final_profit=final,
                )
            )
    else:
        for share, partner in shares:
            partner_lines.append(
                PartnerProfitLine(
                    partner_id=str(partner.partner_id),
                    partner_name=partner.name,
                    daily_share=share.daily_share,
                    partner_pct=Decimal("0.000000"),
                    final_profit=Decimal("0.00"),
                )
            )

    return DailyProfitView(
        on_date=on_date,
        total_capital=total_capital,
        ic_lines=ic_lines,
        partner_lines=partner_lines,
        total_net_profit=total_net,
    )
