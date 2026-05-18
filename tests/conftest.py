"""Pytest fixtures — uses an on-disk SQLite database for fast service tests.

We rebind the engine in :mod:`ordertracker.db.session` so the same
``transactional`` ctx the production code uses also works under tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ordertracker.db import models  # noqa: F401 — register models
from ordertracker.db import session as db_session_mod
from ordertracker.db.base import Base


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", future=True)

    # Ensure FK constraints are enforced under SQLite.
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db_session_mod._engine = engine  # type: ignore[attr-defined]
    db_session_mod._SessionLocal = factory  # type: ignore[attr-defined]
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    s = factory()
    try:
        yield s
    finally:
        s.close()
