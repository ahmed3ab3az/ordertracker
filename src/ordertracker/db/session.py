"""Engine / session factory with pooling, retries, and a transactional ctx manager."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_engine: Engine | None = None
SessionFactory: sessionmaker[Session] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create the global engine + session factory.

    Idempotent: returns the existing engine if already initialised.
    """
    global _engine, SessionFactory
    if _engine is not None:
        return _engine
    _engine = create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        future=True,
    )
    SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Engine not initialised. Call init_engine() first.")
    return _engine


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(OperationalError),
    reraise=True,
)
def _open_session() -> Session:
    if SessionFactory is None:
        raise RuntimeError("SessionFactory not initialised. Call init_engine() first.")
    return SessionFactory()


@contextmanager
def db_session() -> Iterator[Session]:
    """Read-only or manually-managed session — caller decides when to commit."""
    session = _open_session()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transactional() -> Iterator[Session]:
    """Auto-commit on success, rollback on error."""
    session = _open_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
