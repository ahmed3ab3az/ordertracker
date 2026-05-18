"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


user_role = sa.Enum("ADMIN", "PARTNER", name="user_role")
order_status = sa.Enum(
    "NEW", "ON_HOLD", "DELIVERED", "POSTPONED", "RETURNED", name="order_status"
)
day_state = sa.Enum("OPEN", "CLOSED", "REOPENED", name="day_state")
audit_action = sa.Enum(
    "CREATE", "UPDATE", "DELETE", "CLOSE", "REOPEN", "PRINT", "LOGIN", "LOGIN_FAILED",
    name="audit_action",
)
entity_type = sa.Enum(
    "order", "production_company", "importing_company", "partner", "user",
    "day", "partner_share", "snapshot",
    name="entity_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    order_status.create(bind, checkfirst=True)
    day_state.create(bind, checkfirst=True)
    audit_action.create(bind, checkfirst=True)
    entity_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "partners",
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "production_companies",
        sa.Column("pc_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("shipping_cost >= 0", name="ck_production_companies_shipping_cost_nonneg"),
    )

    op.create_table(
        "importing_companies",
        sa.Column("ic_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("profit_per_order", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("day_cost", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("profit_per_order >= 0", name="ck_importing_companies_profit_per_order_nonneg"),
        sa.CheckConstraint("day_cost >= 0", name="ck_importing_companies_day_cost_nonneg"),
    )

    op.create_table(
        "orders",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_key", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", order_status, nullable=False, server_default="NEW"),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("production_company_id", sa.Integer, sa.ForeignKey("production_companies.pc_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("importing_company_id", sa.Integer, sa.ForeignKey("importing_companies.ic_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("print_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_printed_at", sa.DateTime(timezone=True)),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price >= 0", name="ck_orders_price_nonneg"),
        sa.CheckConstraint("print_count >= 0", name="ck_orders_print_count_nonneg"),
    )
    op.create_index("ix_orders_order_key", "orders", ["order_key"], unique=True)
    op.create_index("ix_orders_date", "orders", ["date"])
    op.create_index("ix_orders_date_status", "orders", ["date", "status"])
    op.create_index("ix_orders_date_ic", "orders", ["date", "importing_company_id"])
    op.create_index("ix_orders_date_pc", "orders", ["date", "production_company_id"])

    op.create_table(
        "days",
        sa.Column("day_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date, nullable=False, unique=True),
        sa.Column("state", day_state, nullable=False, server_default="OPEN"),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("reopened_at", sa.DateTime(timezone=True)),
        sa.Column("reopened_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_days_date", "days", ["date"], unique=True)

    op.create_table(
        "daily_partner_shares",
        sa.Column("share_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("partners.partner_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("daily_share", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("partner_id", "date", name="uq_partner_date"),
        sa.CheckConstraint("daily_share >= 0", name="ck_daily_partner_shares_daily_share_nonneg"),
    )
    op.create_index("ix_daily_partner_shares_date", "daily_partner_shares", ["date"])

    op.create_table(
        "daily_ic_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("ic_id", sa.Integer, sa.ForeignKey("importing_companies.ic_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gross_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("day_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("num_delivered", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("date", "ic_id", name="uq_ic_snapshot_date"),
    )
    op.create_index("ix_daily_ic_snapshots_date", "daily_ic_snapshots", ["date"])

    op.create_table(
        "daily_partner_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("partners.partner_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ic_id", sa.Integer, sa.ForeignKey("importing_companies.ic_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("daily_share", sa.Numeric(12, 2), nullable=False),
        sa.Column("partner_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("final_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("date", "partner_id", "ic_id", name="uq_partner_snapshot_date_ic"),
    )
    op.create_index("ix_daily_partner_snapshots_date", "daily_partner_snapshots", ["date"])

    op.create_table(
        "audit_logs",
        sa.Column("log_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("old_values", sa.JSON, nullable=True),
        sa.Column("new_values", sa.JSON, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_daily_partner_snapshots_date", table_name="daily_partner_snapshots")
    op.drop_table("daily_partner_snapshots")
    op.drop_index("ix_daily_ic_snapshots_date", table_name="daily_ic_snapshots")
    op.drop_table("daily_ic_snapshots")
    op.drop_index("ix_daily_partner_shares_date", table_name="daily_partner_shares")
    op.drop_table("daily_partner_shares")
    op.drop_index("ix_days_date", table_name="days")
    op.drop_table("days")

    op.drop_index("ix_orders_date_pc", table_name="orders")
    op.drop_index("ix_orders_date_ic", table_name="orders")
    op.drop_index("ix_orders_date_status", table_name="orders")
    op.drop_index("ix_orders_date", table_name="orders")
    op.drop_index("ix_orders_order_key", table_name="orders")
    op.drop_table("orders")

    op.drop_table("importing_companies")
    op.drop_table("production_companies")
    op.drop_table("partners")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    entity_type.drop(bind, checkfirst=True)
    audit_action.drop(bind, checkfirst=True)
    day_state.drop(bind, checkfirst=True)
    order_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
