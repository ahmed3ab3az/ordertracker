# OrderTracker — Order Tracking & Profit Management

A desktop application (Windows 10/11, PyQt6) for daily order tracking and partner-profit
distribution.

* **Backend**: Neon (PostgreSQL) via SQLAlchemy 2.x + Alembic
* **UI**: PyQt6 — clean, large-button, scanner-friendly
* **Languages**: Arabic (RTL) + English, switchable at runtime
* **Concurrency**: 2–3 PCs, optimistic locking via `updated_at`
* **Auth**: bcrypt passwords, role-based access (`ADMIN` / `PARTNER`), lockout + session timeout
* **Barcodes**: Code128 generated on Excel import
* **Snapshots**: Immutable per-day, per-IC and per-partner profit records
* **Audit log**: append-only, includes old/new JSON state
* **Archiving**: Monthly export to local SQLite + USB backup
* **Auto-update**: GitHub Releases + staging folder + rollback

## Documentation

| Document | Description |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | Layers, deployment model, sync, update flow |
| [`docs/erd.md`](docs/erd.md) | Entity-relationship diagram (Mermaid) |
| [`docs/schema.md`](docs/schema.md) | Per-table column reference, constraints, indexes |
| [`docs/module-plan.md`](docs/module-plan.md) | Python module map and responsibilities |
| [`docs/ui-wireframes.md`](docs/ui-wireframes.md) | Screen-by-screen wireframes |
| [`docs/profit-calculation.md`](docs/profit-calculation.md) | Worked examples of profit math |
| [`docs/state-machine.md`](docs/state-machine.md) | Order and day state transitions |
| [`docs/build-and-release.md`](docs/build-and-release.md) | PyInstaller + Inno Setup + auto-update |
| [`docs/archive-strategy.md`](docs/archive-strategy.md) | Monthly archive + restore procedure |
| [`docs/user-manual-en.md`](docs/user-manual-en.md) | End-user guide (English) |
| [`docs/user-manual-ar.md`](docs/user-manual-ar.md) | دليل المستخدم (Arabic) |

## Quick start (developer)

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Configure DB (Neon connection string)
cp .env.example .env                 # then edit DATABASE_URL

# 3. Migrate & seed
alembic upgrade head
python -m ordertracker.cli.seed      # creates admin user

# 4. Launch
ordertracker
```

## Layout

```
src/ordertracker/
├── app.py            Application entry point
├── config.py         Encrypted credential storage (keyring + Fernet)
├── constants.py      Enums shared across layers
├── db/               SQLAlchemy models + session factory
├── services/         Pure Python business logic (no Qt deps)
├── ui/               PyQt6 widgets, screens, styling
├── i18n/             en.json / ar.json + Translator
├── cli/              Headless CLIs (seed, archive)
└── updater/          Auto-update + rollback runner
docs/                 Architecture, ERDs, manuals
scripts/              Build & packaging
alembic/              DB migrations
tests/                Pytest suite
```

## Cost

$0 — Neon free tier, GitHub Releases for distribution, all packaging tools open-source.

## License

Proprietary © Ahmed Abdelaziz.
