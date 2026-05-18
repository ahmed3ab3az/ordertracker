"""Barcode generation + reprint accounting.

Uses ``python-barcode`` to produce Code128 PNG/SVG payloads. The renderer is
deliberately decoupled from PyQt — UI code converts the bytes into a QPixmap
for display.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from typing import Literal

from barcode import Code128
from barcode.writer import ImageWriter, SVGWriter
from sqlalchemy.orm import Session

from ..constants import REPRINT_WATERMARK_TEXT, AuditAction, EntityType
from ..db.models import Order
from .audit import write_audit

Format = Literal["png", "svg"]


def render_barcode(order_key: str, *, fmt: Format = "png") -> bytes:
    """Render a Code128 barcode for ``order_key`` and return the bytes."""
    writer = ImageWriter() if fmt == "png" else SVGWriter()
    buffer = io.BytesIO()
    Code128(order_key, writer=writer).write(buffer)
    return buffer.getvalue()


def render_slip_payload(
    order: Order,
    *,
    fmt: Format = "png",
    is_reprint: bool,
) -> dict:
    """Return a dict the UI layer can use to draw a printable slip."""
    return {
        "order_key": order.order_key,
        "barcode": render_barcode(order.order_key, fmt=fmt),
        "customer": order.name,
        "address": order.address,
        "price": str(order.price),
        "watermark": REPRINT_WATERMARK_TEXT if is_reprint else None,
    }


def record_print(session: Session, *, order_id: uuid.UUID, actor_user_id: uuid.UUID | None) -> Order:
    """Increment ``print_count`` and stamp ``last_printed_at`` on an order.

    Returns the order so the caller can render it. The audit row marks this
    as a ``PRINT`` action.
    """
    order = session.get(Order, order_id)
    if order is None:
        raise ValueError("Order not found.")
    if order.is_deleted:
        raise ValueError("Cannot reprint a deleted order.")

    before = {"print_count": order.print_count, "last_printed_at": order.last_printed_at}
    order.print_count += 1
    order.last_printed_at = datetime.now(tz=UTC)
    write_audit(
        session,
        user_id=actor_user_id,
        entity_type=EntityType.ORDER,
        entity_id=order.order_id,
        action=AuditAction.PRINT,
        old=before,
        new={"print_count": order.print_count, "last_printed_at": order.last_printed_at},
    )
    session.commit()
    return order
