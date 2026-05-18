# Entity–Relationship Diagram

```mermaid
erDiagram
    USER ||--o| PARTNER : "is partner of"
    PARTNER ||--o{ DAILY_PARTNER_SHARE : "contributes"
    PARTNER ||--o{ DAILY_PARTNER_SNAPSHOT : "earnings frozen as"

    PRODUCTION_COMPANY ||--o{ ORDER : "originates"
    IMPORTING_COMPANY ||--o{ ORDER : "delivers"
    IMPORTING_COMPANY ||--o{ DAILY_IC_SNAPSHOT : "summarised in"
    IMPORTING_COMPANY ||--o{ DAILY_PARTNER_SNAPSHOT : "allocated from"

    DAY ||--o| USER : "closed by"
    DAY ||--o| USER : "reopened by"

    USER ||--o{ AUDIT_LOG : "performs"

    USER {
        uuid    user_id PK
        string  username
        string  password_hash
        enum    role            "ADMIN | PARTNER"
        boolean active
        int     failed_attempts
        ts      locked_until
        ts      last_login_at
        ts      created_at
        ts      updated_at
    }

    PARTNER {
        uuid    partner_id PK
        uuid    user_id    FK
        string  name
        boolean is_deleted
        ts      created_at
        ts      updated_at
    }

    PRODUCTION_COMPANY {
        int     pc_id PK
        string  name
        decimal shipping_cost
        boolean is_deleted
        ts      created_at
        ts      updated_at
    }

    IMPORTING_COMPANY {
        int     ic_id PK
        string  name
        decimal profit_per_order
        decimal day_cost
        boolean is_deleted
        ts      created_at
        ts      updated_at
    }

    ORDER {
        uuid    order_id PK
        string  order_key
        string  name
        string  address
        decimal price
        enum    status      "NEW | ON_HOLD | DELIVERED | POSTPONED | RETURNED"
        date    date
        int     production_company_id FK
        int     importing_company_id  FK
        int     print_count
        ts      last_printed_at
        boolean is_deleted
        ts      created_at
        ts      updated_at
    }

    DAY {
        uuid    day_id PK
        date    date
        enum    state    "OPEN | CLOSED | REOPENED"
        ts      closed_at
        uuid    closed_by FK
        ts      reopened_at
        uuid    reopened_by FK
        ts      created_at
        ts      updated_at
    }

    DAILY_PARTNER_SHARE {
        uuid    share_id PK
        uuid    partner_id FK
        date    date
        decimal daily_share
        ts      created_at
        ts      updated_at
    }

    DAILY_IC_SNAPSHOT {
        uuid    snapshot_id PK
        date    date
        int     ic_id FK
        decimal gross_profit
        decimal day_cost
        decimal net_profit
        int     num_delivered
        ts      created_at
    }

    DAILY_PARTNER_SNAPSHOT {
        uuid    snapshot_id PK
        date    date
        uuid    partner_id FK
        int     ic_id      FK
        decimal daily_share
        decimal partner_pct
        decimal final_profit
        ts      created_at
    }

    AUDIT_LOG {
        uuid    log_id PK
        uuid    user_id FK
        enum    entity_type
        string  entity_id
        enum    action  "CREATE | UPDATE | DELETE | CLOSE | REOPEN | PRINT | LOGIN | LOGIN_FAILED"
        json    old_values
        json    new_values
        ts      timestamp
    }
```

## Relationship cardinalities at a glance

| From | → | To | Cardinality | Notes |
| --- | --- | --- | --- | --- |
| `users` | one-to-zero/one | `partners` | 1 ⇒ 0..1 | only PARTNER role users have a row |
| `production_companies` | one-to-many | `orders` | 1 ⇒ N | enforced by `RESTRICT` FK |
| `importing_companies` | one-to-many | `orders` | 1 ⇒ N (nullable) | NEW orders have no IC yet |
| `partners` | one-to-many | `daily_partner_shares` | 1 ⇒ N | unique on (partner, date) |
| `days` | one-to-zero/one | `users` (closed_by) | 1 ⇒ 0..1 | nullable until closed |
| `daily_ic_snapshots` | one row per | (date, ic_id) | UNIQUE | immutable |
| `daily_partner_snapshots` | one row per | (date, partner, ic) | UNIQUE | immutable |
| `audit_logs` | many-from | `users` | N ⇒ 1 | nullable for system actions |
