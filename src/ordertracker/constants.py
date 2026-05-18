"""Shared constants and enums used across the domain, services, and UI layers."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    PARTNER = "PARTNER"


class OrderStatus(StrEnum):
    NEW = "NEW"
    ON_HOLD = "ON_HOLD"
    DELIVERED = "DELIVERED"
    POSTPONED = "POSTPONED"
    RETURNED = "RETURNED"


class DayState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CLOSE = "CLOSE"
    REOPEN = "REOPEN"
    PRINT = "PRINT"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"


class EntityType(StrEnum):
    ORDER = "order"
    PRODUCTION_COMPANY = "production_company"
    IMPORTING_COMPANY = "importing_company"
    PARTNER = "partner"
    USER = "user"
    DAY = "day"
    PARTNER_SHARE = "partner_share"
    SNAPSHOT = "snapshot"


# -- Security ----------------------------------------------------------------
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 5
SESSION_TIMEOUT_MINUTES = 30
BCRYPT_ROUNDS = 12

# -- Limits ------------------------------------------------------------------
MAX_EXCEL_ROWS = 5_000
DB_RETRY_TIMEOUT_SECONDS = 10
ARCHIVE_RETENTION_YEARS = 3
ARCHIVE_OLDER_THAN_DAYS = 30

# -- Order key formatting ----------------------------------------------------
ORDER_KEY_PREFIX = "ORD"
ORDER_KEY_PC_WIDTH = 2          # PC01, PC02, ...
ORDER_KEY_SEQ_WIDTH = 3         # 001, 002, ... per day
ORDER_KEY_TEMPLATE = "{prefix}-PC{pc:0{pc_w}d}-{mmdd}-{seq:0{seq_w}d}"

# -- Currency ----------------------------------------------------------------
CURRENCY_CODE = "EGP"
CURRENCY_SYMBOL = "EGP"

# -- Reprint watermark -------------------------------------------------------
REPRINT_WATERMARK_TEXT = "REPRINT"

# -- Allowed status transitions ---------------------------------------------
# Format: { from_status: { day_open_targets, day_closed_targets } }
ALLOWED_TRANSITIONS_OPEN_DAY = {
    OrderStatus.NEW: {OrderStatus.ON_HOLD},
    OrderStatus.ON_HOLD: {OrderStatus.DELIVERED, OrderStatus.RETURNED, OrderStatus.POSTPONED},
    OrderStatus.POSTPONED: {OrderStatus.ON_HOLD},
    OrderStatus.DELIVERED: {OrderStatus.RETURNED, OrderStatus.ON_HOLD, OrderStatus.POSTPONED},
    OrderStatus.RETURNED: {OrderStatus.DELIVERED, OrderStatus.ON_HOLD, OrderStatus.POSTPONED},
}

ALLOWED_TRANSITIONS_CLOSED_DAY = {
    # Only POSTPONED orders remain editable on a closed day; they can be reassigned to ON_HOLD.
    OrderStatus.POSTPONED: {OrderStatus.ON_HOLD},
}
