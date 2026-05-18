"""Seed the database with an initial admin account.

Usage::

    python -m ordertracker.cli.seed --username admin --password 'CHANGE-ME'

If no flags are given the script will prompt for input on stdin.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys

from sqlalchemy import select

from ..config import load_config
from ..constants import UserRole
from ..db.models import User
from ..db.session import init_engine, transactional
from ..services.auth import hash_password

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the OrderTracker database.")
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite admin password if it exists.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv or sys.argv[1:])

    cfg = load_config()
    init_engine(cfg.database_url)

    username = args.username or input("Admin username: ").strip()
    password = args.password or getpass.getpass("Admin password: ").strip()
    if not username or not password:
        print("Username and password are required.", file=sys.stderr)
        return 1

    with transactional() as session:
        admin = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if admin is None:
            admin = User(username=username, password_hash=hash_password(password), role=UserRole.ADMIN)
            session.add(admin)
            logger.info("Created admin user %s", username)
        elif args.force:
            admin.password_hash = hash_password(password)
            admin.role = UserRole.ADMIN
            admin.active = True
            logger.info("Reset admin user %s", username)
        else:
            logger.info("Admin user %s already exists. Pass --force to reset.", username)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
