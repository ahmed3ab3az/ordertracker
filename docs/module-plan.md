# Module plan

```
src/ordertracker/
├── __init__.py             — package version
├── __main__.py             — `python -m ordertracker` entry
├── app.py                  — QApplication bootstrap (config + DB + login + main window)
├── constants.py            — enums, transition matrix, limits
├── config.py               — Fernet+keyring encrypted DB URL, AppConfig dataclass
│
├── db/
│   ├── __init__.py         — re-exports
│   ├── base.py             — DeclarativeBase + naming convention
│   ├── session.py          — engine, session factory, retry, transactional ctx
│   └── models.py           — every SQLAlchemy model
│
├── services/               — pure Python; no PyQt imports
│   ├── __init__.py
│   ├── audit.py            — write_audit() helper
│   ├── auth.py             — bcrypt, throttling, SessionInfo
│   ├── order_key.py        — ORD-PC01-MMDD-NNN generation
│   ├── orders.py           — bulk import, IC assign, transitions, optimistic lock
│   ├── companies.py        — PC + IC CRUD, daily stats with balanced-count guard
│   ├── partners.py         — partner CRUD + DailyPartnerShare upsert
│   ├── days.py             — close/reopen + immutable snapshot writes
│   ├── profit.py           — pure functions for live profit math
│   ├── barcode.py          — Code128 PNG/SVG render + reprint accounting
│   ├── excel_import.py     — openpyxl parser, all-or-nothing validation
│   └── archive.py          — export → USB → prune three-phase utility
│
├── ui/
│   ├── __init__.py
│   ├── login_window.py
│   ├── main_window.py      — sidebar + QStackedWidget + idle timer
│   ├── styles/
│   │   └── app.qss
│   └── views/
│       ├── dashboard_view.py
│       ├── orders_view.py
│       ├── companies_view.py
│       ├── partners_view.py
│       ├── shares_view.py
│       ├── day_close_view.py
│       └── settings_view.py
│
├── i18n/
│   ├── __init__.py
│   ├── translator.py       — JSON dict loader, observers, RTL flag
│   ├── en.json
│   └── ar.json
│
├── cli/
│   ├── __init__.py
│   ├── seed.py             — admin bootstrap (`ordertracker-seed`)
│   └── archive.py          — monthly archive (`ordertracker-archive`)
│
└── updater/
    ├── __init__.py
    ├── updater.py          — check / download / install
    └── runner.py           — stand-alone watchdog EXE (rollback on failure)
```

## Why these boundaries?

1. **`services/` knows nothing about Qt.** This means you can unit-test every
   business rule (profit math, transitions, barcode counters, archive flows)
   with plain `pytest` — no `QApplication` required.
2. **`ui/views/` knows nothing about SQLAlchemy.** Every view imports a
   service. If you ever want a CLI mode or a Telegram bot you only need to
   write a new presentation layer.
3. **`config.py` is the only place credentials are decrypted.** Other modules
   call `load_config()` and get a frozen dataclass.
4. **`updater/runner.py` is a separate `__main__`** so PyInstaller compiles
   it as a stand-alone EXE that survives the new install.
