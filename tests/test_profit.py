"""Profit math — end-to-end against a SQLite database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ordertracker.constants import OrderStatus, UserRole
from ordertracker.db.models import (
    DailyPartnerShare,
    ImportingCompany,
    Order,
    Partner,
    ProductionCompany,
    User,
)
from ordertracker.services.profit import compute_daily_profit


def _user(session, name: str) -> User:
    u = User(username=name, password_hash="x", role=UserRole.PARTNER)
    session.add(u)
    session.flush()
    return u


def _partner(session, name: str) -> Partner:
    u = _user(session, name.lower())
    p = Partner(user_id=u.user_id, name=name)
    session.add(p)
    session.flush()
    return p


def _ic(session, name: str, ppo: str, day_cost: str) -> ImportingCompany:
    ic = ImportingCompany(name=name, profit_per_order=Decimal(ppo), day_cost=Decimal(day_cost))
    session.add(ic)
    session.flush()
    return ic


def _pc(session, name: str) -> ProductionCompany:
    pc = ProductionCompany(name=name, shipping_cost=Decimal("0"))
    session.add(pc)
    session.flush()
    return pc


def _order(session, *, pc_id, ic_id, status, day: date, key_seq: int = 1) -> Order:
    o = Order(
        order_key=f"ORD-PC{pc_id:02d}-{day.strftime('%m%d')}-{key_seq:03d}",
        name=f"customer-{key_seq}",
        address="addr",
        price=Decimal("100"),
        status=status,
        date=day,
        production_company_id=pc_id,
        importing_company_id=ic_id,
    )
    session.add(o)
    session.flush()
    return o


def test_single_ic_single_partner(session) -> None:
    pc = _pc(session, "PC1")
    ic = _ic(session, "IC1", "50", "100")
    p = _partner(session, "Ahmed")

    today = date(2026, 1, 15)
    for i in range(20):
        _order(session, pc_id=pc.pc_id, ic_id=ic.ic_id, status=OrderStatus.DELIVERED, day=today, key_seq=i + 1)
    session.add(DailyPartnerShare(partner_id=p.partner_id, date=today, daily_share=Decimal("1000")))
    session.flush()

    view = compute_daily_profit(session, on_date=today)
    [line] = view.ic_lines
    assert line.num_delivered == 20
    assert line.gross_profit == Decimal("1000.00")
    assert line.net_profit == Decimal("900.00")
    assert view.total_net_profit == Decimal("900.00")

    [pl] = view.partner_lines
    assert pl.partner_pct == Decimal("1.000000")
    assert pl.final_profit == Decimal("900.00")


def test_two_partners_split(session) -> None:
    pc = _pc(session, "PC1")
    ic = _ic(session, "IC1", "50", "100")
    a = _partner(session, "Ahmed")
    b = _partner(session, "Bilal")

    today = date(2026, 1, 15)
    for i in range(20):
        _order(session, pc_id=pc.pc_id, ic_id=ic.ic_id, status=OrderStatus.DELIVERED, day=today, key_seq=i + 1)
    session.add(DailyPartnerShare(partner_id=a.partner_id, date=today, daily_share=Decimal("300")))
    session.add(DailyPartnerShare(partner_id=b.partner_id, date=today, daily_share=Decimal("700")))
    session.flush()

    view = compute_daily_profit(session, on_date=today)
    assert view.total_net_profit == Decimal("900.00")
    by_name = {p.partner_name: p for p in view.partner_lines}
    assert by_name["Ahmed"].final_profit == Decimal("270.00")
    assert by_name["Bilal"].final_profit == Decimal("630.00")


def test_zero_delivered_means_no_day_cost(session) -> None:
    pc = _pc(session, "PC1")
    ic = _ic(session, "IC1", "50", "100")
    p = _partner(session, "Ahmed")

    today = date(2026, 1, 15)
    _order(session, pc_id=pc.pc_id, ic_id=ic.ic_id, status=OrderStatus.NEW, day=today, key_seq=1)
    session.add(DailyPartnerShare(partner_id=p.partner_id, date=today, daily_share=Decimal("1000")))
    session.flush()

    view = compute_daily_profit(session, on_date=today)
    [line] = view.ic_lines
    assert line.num_delivered == 0
    assert line.day_cost == Decimal("0.00")
    assert line.net_profit == Decimal("0.00")
    assert view.total_net_profit == Decimal("0.00")
    assert view.partner_lines[0].final_profit == Decimal("0.00")


def test_multi_ic_aggregation(session) -> None:
    pc = _pc(session, "PC1")
    ic_x = _ic(session, "IC-X", "30", "50")
    ic_y = _ic(session, "IC-Y", "40", "100")
    p = _partner(session, "Ahmed")

    today = date(2026, 1, 15)
    for i in range(10):
        _order(session, pc_id=pc.pc_id, ic_id=ic_x.ic_id, status=OrderStatus.DELIVERED, day=today, key_seq=i + 1)
    for i in range(15):
        _order(session, pc_id=pc.pc_id, ic_id=ic_y.ic_id, status=OrderStatus.DELIVERED, day=today, key_seq=100 + i)
    session.add(DailyPartnerShare(partner_id=p.partner_id, date=today, daily_share=Decimal("1000")))
    session.flush()

    view = compute_daily_profit(session, on_date=today)
    by_name = {line.ic_name: line for line in view.ic_lines}
    assert by_name["IC-X"].net_profit == Decimal("250.00")   # 30*10 - 50
    assert by_name["IC-Y"].net_profit == Decimal("500.00")   # 40*15 - 100
    assert view.total_net_profit == Decimal("750.00")
