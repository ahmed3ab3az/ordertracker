# Architecture

OrderTracker is a thick-client desktop application that talks to a single
shared **Neon PostgreSQL** database. Multiple PCs (2–3 office machines)
connect to the same database concurrently. There is no API tier — the client
is the application; the database is the source of truth.

## High-level deployment

```mermaid
flowchart LR
    subgraph Office
        PC1[PC 1<br/>OrderTracker.exe]
        PC2[PC 2<br/>OrderTracker.exe]
        PC3[PC 3<br/>OrderTracker.exe]
    end

    Neon[(Neon PostgreSQL<br/>free tier, never pauses)]
    GH[GitHub Releases<br/>installer + updater EXE]
    USB[(USB Backup<br/>monthly archive)]
    SQLite[(Local SQLite<br/>monthly archive)]

    PC1 -- HTTPS / SSL --> Neon
    PC2 -- HTTPS / SSL --> Neon
    PC3 -- HTTPS / SSL --> Neon

    PC1 -. on launch .-> GH
    PC2 -. on launch .-> GH
    PC3 -. on launch .-> GH

    PC1 -. monthly .-> SQLite
    SQLite -. verified copy .-> USB
```

## Process model on a single PC

```
┌──────────────────────────────────────────┐
│ OrderTracker.exe (Qt event loop)          │
│  ├─ UI: PyQt6 widgets + qss styles        │
│  ├─ Services: pure Python (no Qt deps)    │
│  ├─ SQLAlchemy 2.x + connection pool      │
│  └─ keyring + Fernet (encrypted DB URL)   │
└──────────────────────────────────────────┘
              │ launches
              ▼
┌──────────────────────────────────────────┐
│ updater_runner.exe (only during updates) │
│  ├─ Monitors new install                  │
│  └─ Restores .ordertracker-rollback/     │
│     if startup fails within 30s           │
└──────────────────────────────────────────┘
```

## Layered code structure

```
┌───────────────────────────────────────────────────────┐
│  Presentation layer (PyQt6)                           │
│  src/ordertracker/ui/                                 │
│   ├── main_window.py        — sidebar + stack         │
│   ├── login_window.py       — login dialog            │
│   └── views/                — one widget per screen   │
└───────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│  Service layer (no UI imports here)                   │
│  src/ordertracker/services/                           │
│   ├── auth.py        ├── orders.py    ├── days.py     │
│   ├── companies.py   ├── partners.py  ├── audit.py    │
│   ├── profit.py      ├── archive.py   ├── barcode.py  │
│   ├── excel_import.py                ├── order_key.py │
└───────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│  Data layer (SQLAlchemy 2.x)                          │
│  src/ordertracker/db/                                 │
│   ├── models.py             ├── session.py            │
│   └── base.py                                         │
└───────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  Neon Postgres   │
                  └──────────────────┘
```

## Concurrency

Two PCs may edit the same order simultaneously. We use **optimistic locking**:

1. The `Order` row has an `updated_at` timestamp that the DB updates on every
   write.
2. The UI loads the row and remembers `updated_at` at that moment.
3. On save the service compares the stored value against the in-memory one.
4. If they differ → `ConcurrentEditError` is raised and the UI tells the user
   to refresh.

This avoids row-level DB locks (which would not work across Neon's
connection pooler anyway).

## Sessions and security

| Concern | Solution |
| --- | --- |
| Password storage | `bcrypt` (cost 12) |
| Login throttling | 5 failed attempts → 5-minute lock; counter resets on success |
| Session timeout | 30 minutes of UI inactivity → forced logout |
| Connection string | Encrypted with Fernet, key stored in OS keyring |
| TLS | Neon enforces SSL on every connection |
| Audit log | Append-only; no DELETE rights granted to the role used by the app |

## Update flow

```mermaid
sequenceDiagram
    autonumber
    participant App as OrderTracker.exe
    participant GH as GitHub Releases
    participant Run as updater_runner.exe
    participant FS as Install folder

    App->>GH: GET /releases/latest
    GH-->>App: tag, asset URL, SHA-256
    alt update available
        App->>App: download installer to staging
        App->>App: verify SHA-256
        App->>FS: snapshot install folder → ./.ordertracker-rollback
        App->>FS: launch installer (silent)
        App->>App: exit
        FS->>App: new OrderTracker.exe written
        Run->>App: start new version
        alt boot succeeds within 30s
            Run->>FS: delete .ordertracker-rollback
        else boot fails
            Run->>FS: restore .ordertracker-rollback
        end
    else up to date
        App-->>App: notify user
    end
```

## Daily order lifecycle

```mermaid
sequenceDiagram
    participant Staff as Office staff
    participant App
    participant DB as Neon Postgres

    Staff->>App: drag Excel onto window
    App->>App: parse + validate rows
    App->>DB: bulk insert orders (NEW), generate barcodes
    Staff->>App: select order, click "Assign IC"
    App->>DB: order.status = ON_HOLD, importing_company_id set
    Note over Staff,App: ... deliveries happen during the day ...
    Staff->>App: scan returned barcodes → RETURNED
    Staff->>App: confirm postponed → POSTPONED
    Staff->>App: bulk-mark rest as DELIVERED
    Staff->>App: click "Close Day"
    App->>App: validate (no ON_HOLD/NEW left)
    App->>DB: write daily_ic_snapshots + daily_partner_snapshots
    App->>DB: days.state = CLOSED
```

## Archiving flow

```mermaid
flowchart LR
    Cloud[(Neon Postgres)] -- export (read-only) --> SQLite[(SQLite file)]
    SQLite -- SHA-256 verify --> USB[(USB drive)]
    USB -- ok --> Prune[Delete rows ≥ 30 days from Cloud]
```

If any step fails, the cloud rows are **not** deleted.
