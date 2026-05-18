"""Order key generation tests."""

from __future__ import annotations

from datetime import date

from ordertracker.services.order_key import build_order_key


def test_format_matches_spec() -> None:
    assert build_order_key(pc_id=1, on_date=date(2025, 5, 17), seq=1) == "ORD-PC01-0517-001"
    assert build_order_key(pc_id=2, on_date=date(2025, 12, 31), seq=42) == "ORD-PC02-1231-042"


def test_zero_padding_widths() -> None:
    assert build_order_key(pc_id=12, on_date=date(2025, 1, 1), seq=999) == "ORD-PC12-0101-999"


def test_sequential_monotone() -> None:
    keys = [
        build_order_key(pc_id=1, on_date=date(2025, 5, 17), seq=s) for s in range(1, 4)
    ]
    assert keys == ["ORD-PC01-0517-001", "ORD-PC01-0517-002", "ORD-PC01-0517-003"]
