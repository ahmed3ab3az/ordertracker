"""Monthly archive utility.

Exports records older than :data:`constants.ARCHIVE_OLDER_THAN_DAYS` to a local
SQLite file, verifies a SHA-256 checksum, optionally copies to a USB target,
then deletes the records from Postgres only after the USB copy is confirmed.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..constants import ARCHIVE_OLDER_THAN_DAYS, AuditAction, EntityType
from ..db.models import (
    AuditLog,
    DailyICSnapshot,
    DailyPartnerShare,
    DailyPartnerSnapshot,
    Day,
    Order,
)
from .audit import write_audit

logger = logging.getLogger(__name__)


@dataclass
class ArchiveResult:
    archive_path: Path
    checksum: str
    records: dict[str, int]
    usb_copy_path: Path | None


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(2**16), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _cutoff_date() -> date:
    return (datetime.now(tz=UTC) - timedelta(days=ARCHIVE_OLDER_THAN_DAYS)).date()


# Tables to copy + the column used to filter by date.
ARCHIVED_TABLES: list[tuple[type, str]] = [
    (Order, "date"),
    (Day, "date"),
    (DailyPartnerShare, "date"),
    (DailyICSnapshot, "date"),
    (DailyPartnerSnapshot, "date"),
    (AuditLog, "timestamp"),
]


def export_archive(
    session: Session,
    *,
    archive_dir: Path,
    cutoff: date | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> ArchiveResult:
    """Phase 1: read-only export to ``archive_dir/ordertracker_<YYYYMM>.sqlite``."""
    cutoff = cutoff or _cutoff_date()
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = cutoff.strftime("%Y%m")
    archive_path = archive_dir / f"ordertracker_{stamp}.sqlite"

    if archive_path.exists():
        archive_path.unlink()  # always overwrite — Phase-3 delete is the destructive step

    with sqlite3.connect(archive_path) as conn:
        records: dict[str, int] = {}
        for model, date_col in ARCHIVED_TABLES:
            table_name = model.__tablename__
            columns = [c.name for c in model.__table__.columns]
            ddl = ", ".join(f"{c} TEXT" for c in columns)
            conn.execute(f"CREATE TABLE {table_name} ({ddl})")

            col = getattr(model, date_col)
            cutoff_value = (
                datetime.combine(cutoff, datetime.min.time(), tzinfo=UTC)
                if date_col == "timestamp"
                else cutoff
            )
            rows = session.execute(select(model).where(col < cutoff_value)).scalars().all()
            for row in rows:
                values = [getattr(row, c) for c in columns]
                conn.execute(
                    f"INSERT INTO {table_name} VALUES ({', '.join(['?'] * len(columns))})",
                    [None if v is None else str(v) for v in values],
                )
            records[table_name] = len(rows)
        conn.commit()

    checksum = _sha256(archive_path)
    (archive_path.with_suffix(".sha256")).write_text(checksum, encoding="utf-8")
    if actor_user_id is not None:
        write_audit(
            session,
            user_id=actor_user_id,
            entity_type=EntityType.DAY,
            entity_id="-",
            action=AuditAction.CREATE,
            new={"archive_path": str(archive_path), "records": records, "checksum": checksum},
        )
        session.commit()
    return ArchiveResult(archive_path=archive_path, checksum=checksum, records=records, usb_copy_path=None)


def copy_to_usb(result: ArchiveResult, *, usb_target: Path) -> ArchiveResult:
    """Phase 2: copy + re-verify SHA-256 on the USB target."""
    usb_target.mkdir(parents=True, exist_ok=True)
    dest = usb_target / result.archive_path.name
    shutil.copy2(result.archive_path, dest)
    shutil.copy2(result.archive_path.with_suffix(".sha256"), dest.with_suffix(".sha256"))
    if _sha256(dest) != result.checksum:
        dest.unlink(missing_ok=True)
        raise RuntimeError("USB checksum mismatch — refusing to proceed.")
    return ArchiveResult(
        archive_path=result.archive_path,
        checksum=result.checksum,
        records=result.records,
        usb_copy_path=dest,
    )


def prune_cloud(
    session: Session,
    *,
    cutoff: date | None = None,
    require_usb_copy: ArchiveResult | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Phase 3: delete the archived rows from Postgres."""
    if require_usb_copy is None or require_usb_copy.usb_copy_path is None:
        raise RuntimeError("USB copy is required before pruning the cloud database.")

    cutoff = cutoff or _cutoff_date()
    deleted: dict[str, int] = {}
    for model, date_col in ARCHIVED_TABLES:
        col = getattr(model, date_col)
        cutoff_value = (
            datetime.combine(cutoff, datetime.min.time(), tzinfo=UTC)
            if date_col == "timestamp"
            else cutoff
        )
        result = session.execute(delete(model).where(col < cutoff_value))
        deleted[model.__tablename__] = result.rowcount or 0

    if actor_user_id is not None:
        write_audit(
            session,
            user_id=actor_user_id,
            entity_type=EntityType.DAY,
            entity_id="-",
            action=AuditAction.DELETE,
            new={"pruned_before": cutoff.isoformat(), "deleted": deleted},
        )
    session.commit()
    return deleted
