"""Stand-alone updater watchdog.

Compiled separately into ``updater_runner.exe`` so it survives self-update.
Run after the main installer finishes; if the new binary fails to launch
within 30 s it restores ``./.ordertracker-rollback``.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--install-dir", type=Path, required=True)
    p.add_argument("--main-exe", required=True, help="Filename of the main EXE inside install-dir.")
    p.add_argument("--timeout", type=int, default=30)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse(argv or sys.argv[1:])

    install_dir = args.install_dir.resolve()
    main_exe = install_dir / args.main_exe
    rollback = install_dir.parent / ".ordertracker-rollback"

    if not main_exe.exists():
        logger.error("New binary missing at %s — rolling back.", main_exe)
        _rollback(install_dir, rollback)
        return 2

    logger.info("Starting %s", main_exe)
    try:
        proc = subprocess.Popen([str(main_exe)])
    except OSError as exc:
        logger.error("Failed to start: %s", exc)
        _rollback(install_dir, rollback)
        return 3

    start = time.time()
    while time.time() - start < args.timeout:
        rc = proc.poll()
        if rc is None:
            time.sleep(1)
            continue
        if rc == 0:
            logger.info("Process exited cleanly during boot — leaving install in place.")
            return 0
        logger.warning("New binary exited with rc=%s — rolling back.", rc)
        _rollback(install_dir, rollback)
        return 4

    logger.info("Update healthy after %ss.", args.timeout)
    if rollback.exists():
        shutil.rmtree(rollback)
    return 0


def _rollback(install_dir: Path, rollback: Path) -> None:
    if not rollback.exists():
        logger.error("No rollback snapshot at %s.", rollback)
        return
    logger.info("Restoring %s ← %s", install_dir, rollback)
    shutil.rmtree(install_dir, ignore_errors=True)
    shutil.copytree(rollback, install_dir)


if __name__ == "__main__":
    raise SystemExit(main())
