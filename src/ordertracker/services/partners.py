"""Partner + daily-share services."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import AuditAction, EntityType, UserRole
from ..db.models import DailyPartnerShare, Partner, User
from .audit import write_audit
from .auth import hash_password


class PartnerService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- CRUD ----------------------------------------------------------------
    def list_active(self) -> list[Partner]:
        return list(
            self.session.execute(
                select(Partner).where(Partner.is_deleted.is_(False)).order_by(Partner.name)
            ).scalars()
        )

    def create(
        self, *, name: str, username: str, password: str, actor_user_id: uuid.UUID
    ) -> Partner:
        if self.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none():
            raise ValueError("Username already exists.")

        user = User(
            username=username.strip(),
            password_hash=hash_password(password),
            role=UserRole.PARTNER,
            active=True,
        )
        self.session.add(user)
        self.session.flush()

        partner = Partner(user_id=user.user_id, name=name.strip())
        self.session.add(partner)
        self.session.flush()

        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.PARTNER,
            entity_id=partner.partner_id,
            action=AuditAction.CREATE,
            new={"name": partner.name, "username": user.username},
        )
        self.session.commit()
        return partner

    def reset_password(
        self, *, partner_id: uuid.UUID, new_password: str, actor_user_id: uuid.UUID
    ) -> None:
        partner = self.session.get(Partner, partner_id)
        if partner is None or partner.is_deleted:
            raise ValueError("Partner not found.")
        partner.user.password_hash = hash_password(new_password)
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.USER,
            entity_id=partner.user.user_id,
            action=AuditAction.UPDATE,
            new={"password_reset": True},
        )
        self.session.commit()

    def soft_delete(self, *, partner_id: uuid.UUID, actor_user_id: uuid.UUID) -> None:
        partner = self.session.get(Partner, partner_id)
        if partner is None or partner.is_deleted:
            return
        partner.is_deleted = True
        partner.user.active = False
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.PARTNER,
            entity_id=partner.partner_id,
            action=AuditAction.DELETE,
            new={"is_deleted": True},
        )
        self.session.commit()


class DailyPartnerShareService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_date(self, *, on_date: date) -> list[DailyPartnerShare]:
        return list(
            self.session.execute(
                select(DailyPartnerShare).where(DailyPartnerShare.date == on_date)
            ).scalars()
        )

    def total_capital(self, *, on_date: date) -> Decimal:
        return sum(
            (s.daily_share for s in self.list_for_date(on_date=on_date)), start=Decimal("0.00")
        )

    def upsert(
        self,
        *,
        partner_id: uuid.UUID,
        on_date: date,
        daily_share: Decimal,
        actor_user_id: uuid.UUID,
    ) -> DailyPartnerShare:
        existing = self.session.execute(
            select(DailyPartnerShare).where(
                DailyPartnerShare.partner_id == partner_id,
                DailyPartnerShare.date == on_date,
            )
        ).scalar_one_or_none()

        if existing is None:
            row = DailyPartnerShare(
                partner_id=partner_id, date=on_date, daily_share=daily_share
            )
            self.session.add(row)
            self.session.flush()
            write_audit(
                self.session,
                user_id=actor_user_id,
                entity_type=EntityType.PARTNER_SHARE,
                entity_id=row.share_id,
                action=AuditAction.CREATE,
                new={"daily_share": str(daily_share), "date": on_date.isoformat()},
            )
            self.session.commit()
            return row

        before = {"daily_share": str(existing.daily_share)}
        existing.daily_share = daily_share
        write_audit(
            self.session,
            user_id=actor_user_id,
            entity_type=EntityType.PARTNER_SHARE,
            entity_id=existing.share_id,
            action=AuditAction.UPDATE,
            old=before,
            new={"daily_share": str(daily_share)},
        )
        self.session.commit()
        return existing
