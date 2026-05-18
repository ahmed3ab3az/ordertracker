# Database schema reference

All tables live in the default `public` schema. Identifiers are snake_case.
Timestamps are `TIMESTAMP WITH TIME ZONE` and default to `NOW()` server-side.
Decimals use `NUMERIC(12, 2)` unless otherwise noted.

> Naming conventions for constraints follow Alembic best practice
> (see [`src/ordertracker/db/base.py`](../src/ordertracker/db/base.py)).

## Enumerations

| Name | Values |
| --- | --- |
| `user_role` | `ADMIN`, `PARTNER` |
| `order_status` | `NEW`, `ON_HOLD`, `DELIVERED`, `POSTPONED`, `RETURNED` |
| `day_state` | `OPEN`, `CLOSED`, `REOPENED` |
| `audit_action` | `CREATE`, `UPDATE`, `DELETE`, `CLOSE`, `REOPEN`, `PRINT`, `LOGIN`, `LOGIN_FAILED` |
| `entity_type` | `order`, `production_company`, `importing_company`, `partner`, `user`, `day`, `partner_share`, `snapshot` |

## Tables

### `users`

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `user_id` | uuid | PK | |
| `username` | varchar(64) | UNIQUE, NOT NULL | indexed |
| `password_hash` | varchar(255) | NOT NULL | bcrypt |
| `role` | `user_role` | NOT NULL | |
| `active` | boolean | NOT NULL, default true | soft-delete |
| `failed_attempts` | int | NOT NULL, default 0 | resets on success |
| `locked_until` | timestamptz | nullable | enforced by service layer |
| `last_login_at` | timestamptz | nullable | |
| `created_at` | timestamptz | NOT NULL, default now() | |
| `updated_at` | timestamptz | NOT NULL, default now() | |

### `partners`

| Column | Type | Constraints |
| --- | --- | --- |
| `partner_id` | uuid | PK |
| `user_id` | uuid | UNIQUE, FK → users.user_id (ON DELETE RESTRICT) |
| `name` | varchar(128) | NOT NULL |
| `is_deleted` | boolean | NOT NULL, default false |
| `created_at`, `updated_at` | timestamptz | NOT NULL, default now() |

### `production_companies`

| Column | Type | Constraints |
| --- | --- | --- |
| `pc_id` | int | PK, autoincrement (used in `order_key`) |
| `name` | varchar(128) | UNIQUE, NOT NULL |
| `shipping_cost` | numeric(12,2) | NOT NULL, default 0, **CHECK ≥ 0** |
| `is_deleted` | boolean | NOT NULL, default false |
| `created_at`, `updated_at` | timestamptz | NOT NULL, default now() |

> `shipping_cost` is tracked for reporting only; it is **never** deducted
> from profit (per spec).

### `importing_companies`

| Column | Type | Constraints |
| --- | --- | --- |
| `ic_id` | int | PK, autoincrement |
| `name` | varchar(128) | UNIQUE, NOT NULL |
| `profit_per_order` | numeric(12,2) | NOT NULL, default 0, **CHECK ≥ 0** |
| `day_cost` | numeric(12,2) | NOT NULL, default 0, **CHECK ≥ 0** |
| `is_deleted` | boolean | NOT NULL, default false |

### `orders`

| Column | Type | Constraints |
| --- | --- | --- |
| `order_id` | uuid | PK |
| `order_key` | varchar(32) | UNIQUE, NOT NULL, indexed |
| `name` | varchar(255) | NOT NULL |
| `address` | text | NOT NULL |
| `price` | numeric(12,2) | NOT NULL, **CHECK ≥ 0** |
| `status` | `order_status` | NOT NULL, default `NEW` |
| `date` | date | NOT NULL, indexed |
| `production_company_id` | int | NOT NULL, FK → production_companies.pc_id (RESTRICT) |
| `importing_company_id` | int | nullable, FK → importing_companies.ic_id (RESTRICT) |
| `print_count` | int | NOT NULL, default 0, **CHECK ≥ 0** |
| `last_printed_at` | timestamptz | nullable |
| `is_deleted` | boolean | NOT NULL, default false |
| `created_at`, `updated_at` | timestamptz | NOT NULL, default now() |

Indexes:

* `ix_orders_date_status` on (`date`, `status`)
* `ix_orders_date_ic` on (`date`, `importing_company_id`)
* `ix_orders_date_pc` on (`date`, `production_company_id`)

### `days`

| Column | Type | Constraints |
| --- | --- | --- |
| `day_id` | uuid | PK |
| `date` | date | UNIQUE, NOT NULL, indexed |
| `state` | `day_state` | NOT NULL, default `OPEN` |
| `closed_at` | timestamptz | nullable |
| `closed_by` | uuid | nullable, FK → users.user_id (SET NULL) |
| `reopened_at` | timestamptz | nullable |
| `reopened_by` | uuid | nullable, FK → users.user_id (SET NULL) |

### `daily_partner_shares`

| Column | Type | Constraints |
| --- | --- | --- |
| `share_id` | uuid | PK |
| `partner_id` | uuid | NOT NULL, FK → partners.partner_id (RESTRICT) |
| `date` | date | NOT NULL, indexed |
| `daily_share` | numeric(12,2) | NOT NULL, default 0, **CHECK ≥ 0** |

UNIQUE (`partner_id`, `date`) — one share per partner per day.

### `daily_ic_snapshots`

| Column | Type | Constraints |
| --- | --- | --- |
| `snapshot_id` | uuid | PK |
| `date` | date | NOT NULL, indexed |
| `ic_id` | int | NOT NULL, FK → importing_companies.ic_id (RESTRICT) |
| `gross_profit` | numeric(14,2) | NOT NULL |
| `day_cost` | numeric(14,2) | NOT NULL |
| `net_profit` | numeric(14,2) | NOT NULL |
| `num_delivered` | int | NOT NULL |

UNIQUE (`date`, `ic_id`) — append-only; no UPDATE/DELETE expected.

### `daily_partner_snapshots`

| Column | Type | Constraints |
| --- | --- | --- |
| `snapshot_id` | uuid | PK |
| `date` | date | NOT NULL, indexed |
| `partner_id` | uuid | NOT NULL, FK → partners.partner_id (RESTRICT) |
| `ic_id` | int | NOT NULL, FK → importing_companies.ic_id (RESTRICT) |
| `daily_share` | numeric(12,2) | NOT NULL |
| `partner_pct` | numeric(8,6) | NOT NULL |
| `final_profit` | numeric(14,2) | NOT NULL |

UNIQUE (`date`, `partner_id`, `ic_id`) — one row per partner per IC per day.

### `audit_logs`

| Column | Type | Constraints |
| --- | --- | --- |
| `log_id` | uuid | PK |
| `user_id` | uuid | nullable, FK → users.user_id (SET NULL) |
| `entity_type` | `entity_type` | NOT NULL |
| `entity_id` | varchar(64) | NOT NULL — string form of UUID/integer/`-` |
| `action` | `audit_action` | NOT NULL |
| `old_values` | jsonb | nullable |
| `new_values` | jsonb | nullable |
| `timestamp` | timestamptz | NOT NULL, default now(), indexed |

Indexes:

* `ix_audit_logs_timestamp` on (`timestamp`)
* `ix_audit_entity` on (`entity_type`, `entity_id`)

## Recommended database role

Create a least-privilege role that the application uses at runtime:

```sql
CREATE ROLE ordertracker_app LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE ordertracker TO ordertracker_app;
GRANT USAGE ON SCHEMA public TO ordertracker_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ordertracker_app;
REVOKE DELETE ON audit_logs FROM ordertracker_app;
REVOKE UPDATE, DELETE ON daily_ic_snapshots, daily_partner_snapshots FROM ordertracker_app;
```

The archive CLI uses a separate role with explicit `DELETE` on the
archived tables.
