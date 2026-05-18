"""Append-only audit log writer."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..constants import AuditAction, EntityType
from ..db.models import AuditLog


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "isoformat"):  # date, datetime
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value") and hasattr(value, "name"):  # Enum
        return value.value
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def write_audit(
    session: Session,
    *,
    user_id: uuid.UUID | None,
    entity_type: EntityType,
    entity_id: str | uuid.UUID,
    action: AuditAction,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist a single audit record. Caller controls the surrounding transaction."""
    log = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_values=_to_jsonable(old) if old else None,
        new_values=_to_jsonable(new) if new else None,
    )
    session.add(log)
    return log
