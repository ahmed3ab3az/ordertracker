"""Order key generation.

Format: ``ORD-PC{pc:02}-{MMDD}-{seq:03}``

The sequential counter is **global per day** — it does NOT restart per PC.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import (
    ORDER_KEY_PC_WIDTH,
    ORDER_KEY_PREFIX,
    ORDER_KEY_SEQ_WIDTH,
    ORDER_KEY_TEMPLATE,
)
from ..db.models import Order


def build_order_key(*, pc_id: int, on_date: date, seq: int) -> str:
    return ORDER_KEY_TEMPLATE.format(
        prefix=ORDER_KEY_PREFIX,
        pc=pc_id,
        pc_w=ORDER_KEY_PC_WIDTH,
        mmdd=on_date.strftime("%m%d"),
        seq=seq,
        seq_w=ORDER_KEY_SEQ_WIDTH,
    )


def next_daily_seq(session: Session, on_date: date) -> int:
    """Return the next 1-based sequential number for ``on_date``.

    Counts existing rows (including soft-deleted) so reused keys are impossible.
    """
    current = session.execute(
        select(func.count(Order.order_id)).where(Order.date == on_date)
    ).scalar_one()
    return int(current) + 1


def reserve_keys(session: Session, *, pc_id: int, on_date: date, count: int) -> list[str]:
    """Allocate ``count`` consecutive order keys for the given PC + date."""
    start = next_daily_seq(session, on_date)
    return [build_order_key(pc_id=pc_id, on_date=on_date, seq=start + i) for i in range(count)]
