"""Monthly archive CLI: export → USB copy → prune."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..config import load_config
from ..db.session import init_engine, transactional
from ..services.archive import copy_to_usb, export_archive, prune_cloud

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive old records to SQLite + USB.")
    parser.add_argument("--usb-target", type=Path, required=True, help="Mounted USB drive path.")
    parser.add_argument(
        "--skip-prune",
        action="store_true",
        help="Stop after USB copy — do NOT delete archived rows from Postgres.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv or sys.argv[1:])

    cfg = load_config()
    init_engine(cfg.database_url)

    with transactional() as session:
        result = export_archive(session, archive_dir=cfg.archive_dir)
        logger.info("Exported to %s (checksum %s)", result.archive_path, result.checksum[:16])

        verified = copy_to_usb(result, usb_target=args.usb_target)
        logger.info("Copied to USB %s", verified.usb_copy_path)

        if args.skip_prune:
            logger.info("Skipping prune. Done.")
            return 0

        deleted = prune_cloud(session, require_usb_copy=verified)
        for table, n in deleted.items():
            logger.info("Pruned %s: %s rows", table, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
