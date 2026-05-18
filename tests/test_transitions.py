"""Sanity checks for the order state-machine matrices."""

from __future__ import annotations

from ordertracker.constants import (
    ALLOWED_TRANSITIONS_CLOSED_DAY,
    ALLOWED_TRANSITIONS_OPEN_DAY,
    OrderStatus,
)


def test_new_only_to_on_hold() -> None:
    assert ALLOWED_TRANSITIONS_OPEN_DAY[OrderStatus.NEW] == {OrderStatus.ON_HOLD}


def test_on_hold_targets() -> None:
    assert ALLOWED_TRANSITIONS_OPEN_DAY[OrderStatus.ON_HOLD] == {
        OrderStatus.DELIVERED,
        OrderStatus.RETURNED,
        OrderStatus.POSTPONED,
    }


def test_closed_day_only_postponed() -> None:
    assert {OrderStatus.POSTPONED: {OrderStatus.ON_HOLD}} == ALLOWED_TRANSITIONS_CLOSED_DAY


def test_postponed_loops_back_to_on_hold() -> None:
    assert OrderStatus.ON_HOLD in ALLOWED_TRANSITIONS_OPEN_DAY[OrderStatus.POSTPONED]


def test_no_transition_into_new() -> None:
    # NEW is only created — never transitioned to.
    for status, targets in ALLOWED_TRANSITIONS_OPEN_DAY.items():
        assert OrderStatus.NEW not in targets, f"{status} should not move back to NEW"
