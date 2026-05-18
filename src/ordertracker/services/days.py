"""Day open/close mechanics + immutable snapshot persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import AuditAction, DayState, EntityType, OrderStatus
from ..db.models import (
    DailyICSnapshot,
    DailyPartnerSnapshot,
    Day,
    Order,
)
from .audit import write_audit
from .profit import compute_daily_profit


class DayValidationError(Exception):
    pass


class DayService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ----------------------------------------------------------- BASIC LOOKUP
    def get_or_create(self, on_date: date) -> Day:
        day = self.session.execute(select(Day).where(Day.date == on_date)).scalar_one_or_none()
        if day is None:
            day = Day(date=on_date, state=DayState.OPEN)
            self.session.add(day)
            self.session.flush()
        return day

    def state(self, on_date: date) -> DayState:
        day = self.session.execute(select(Day).where(Day.date == on_date)).scalar_one_or_none()
        return day.state if day else DayState.OPEN

    # ---------------------------------------------------------------- CLOSING
    def close(self, *, on_date: date, actor_user_id: uuid.UUID) -> Day:
        # 1. Validate: nothing can still be in ON_HOLD or NEW.
        leftover = self.session.execute(
            select(Order).where(
                Order.date == on_date,
                Order.is_deleted.is_(False),
                Order.status.in_([OrderStatus.NEW, OrderStatus.ON_HOLD]),
            )
        ).scalars().first()
        if leftover is not None:
            raise DayValidationError(
                "Cannot close the day while there are NEW or ON_HOLD orders remaining."
            )

        day = self.get_or_create(on_date)

        # 2. Compute and freeze snapshots.
        view = compute_daily_profit(self.session, on_date=on_date)
        for line in view.ic_lines:
            existing = self.session.execute(
                select(DailyICSnapshot).where(
                    DailyICSnapshot.date == on_date,
                    DailyICSnapshot.ic_id == line.ic_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue  # snapshots are append-only
            self.session.add(
                DailyICSnapshot(
                    date=on_date,
                    ic_id=line.ic_id,
                    gross_profit=line.gross_profit,
                    day_cost=line.day_cost,
                    net_profit=line.net_profit,
                    num_delivered=line.num_delivered,
                )
            )

        for line in view.partner_lines:
            # Persist one snapshot per IC, distributing the IC net by the partner pct.
            for ic in view.ic_lines:
                existing = self.session.execute(
                    select(DailyPartnerSnapshot).where(
                        DailyPartnerSnapshot.date == on_date,
                        DailyPartnerSnapshot.partner_id == uuid.UUID(line.partner_id),
                        DailyPartnerSnapshot.ic_id == ic.ic_id,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    continue
                final_for_ic = (ic.net_profit * line.partner_pct).quantize(line.final_profit)
                self.session.add(
                    DailyPartnerSnapshot(
                        date=on_date,
                        partner_id=uuid.UUID(line.partner_id),
                        ic_id=ic.ic_id,
                        daily_share=line.daily_share,
                        partner_pct=line.partner_pct,
                        final_profit=final_for_ic,
                    )
                )

        # 3. Update day state.
        day.state = DayState.CLOSED
        day.closed_at = datetime.now(tz=UTC)
        day.closed_by = actor_user_id

        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.DAY,
            entity_id=day.day_id,
            action=AuditAction.CLOSE,
            new={
                "date": on_date.isoformat(),
                "ic_snapshots": len(view.ic_lines),
                "partner_snapshots": len(view.partner_lines),
            },
        )
        self.session.commit()
        return day

    def reopen(self, *, on_date: date, actor_user_id: uuid.UUID) -> Day:
        day = self.session.execute(select(Day).where(Day.date == on_date)).scalar_one_or_none()
        if day is None or day.state == DayState.OPEN:
            raise DayValidationError("Day is not closed; nothing to reopen.")
        day.state = DayState.REOPENED
        day.reopened_at = datetime.now(tz=UTC)
        day.reopened_by = actor_user_id
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.DAY,
            entity_id=day.day_id,
            action=AuditAction.REOPEN,
            new={"date": on_date.isoformat()},
        )
        self.session.commit()
        return day
