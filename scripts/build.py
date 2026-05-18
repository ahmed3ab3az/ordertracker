"""End-to-end Windows build script.

Runs:

1. ``pyinstaller ordertracker.spec`` — packages the main app + the updater runner.
2. ``iscc installer/ordertracker.iss`` — wraps the dist into a Windows installer.

The Inno Setup compiler (``iscc``) must be on PATH. On a dev machine you can
install it from https://jrsoftware.org/isdl.php.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build OrderTracker installer.")
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv or sys.argv[1:])

    if args.clean:
        for p in ("build", "dist"):
            shutil.rmtree(REPO_ROOT / p, ignore_errors=True)

    _run([sys.executable, "-m", "PyInstaller", "scripts/ordertracker.spec", "--noconfirm"])

    if args.skip_installer:
        return 0

    iscc = shutil.which("iscc")
    if iscc is None:
        print(
            "Inno Setup compiler (iscc) not found on PATH. Skipping installer step.",
            file=sys.stderr,
        )
        return 0
    _run([iscc, "installer/ordertracker.iss"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
