"""Auto-update client.

Workflow:

1. Query ``GET https://api.github.com/repos/<owner>/<repo>/releases/latest``.
2. Compare the tag against the embedded ``__version__``.
3. Download the ``ordertracker-setup-x.y.z.exe`` asset to a staging folder.
4. Verify the SHA-256 from the release notes.
5. Persist the previous installation as a rollback snapshot.
6. Run the new installer with ``/SILENT /SUPPRESSMSGBOXES`` and exit.
7. The bundled ``updater_runner.exe`` watches the install — on failure it
   restores the rollback snapshot.

This module only handles steps 1-4. The native installer launch is handled
by :mod:`updater.runner` which lives next to the EXE so it survives self-update.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests
from packaging.version import Version

from .. import __version__

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
DEFAULT_REPO = os.environ.get("ORDERTRACKER_RELEASES_REPO", "ahmed3ab3az/ordertracker")
ASSET_RE = re.compile(r"ordertracker-setup-(?P<version>\d+\.\d+\.\d+)\.exe$", re.IGNORECASE)
SHA_RE = re.compile(r"SHA256:\s*([a-fA-F0-9]{64})")


class UpdateError(Exception):
    pass


@dataclass
class UpdateResult:
    current_version: str
    latest_version: str
    update_available: bool
    download_url: str | None = None
    expected_sha256: str | None = None


def _fetch_release(repo: str) -> dict:
    response = requests.get(GITHUB_API.format(repo=repo), timeout=10)
    if response.status_code == 404:
        raise UpdateError("No GitHub release published yet.")
    response.raise_for_status()
    return response.json()


def check_for_update(*, repo: str = DEFAULT_REPO, current: str | None = None) -> UpdateResult:
    current_v = Version(current or __version__)
    try:
        release = _fetch_release(repo)
    except (requests.RequestException, UpdateError) as exc:
        raise UpdateError(f"Cannot check for updates: {exc}") from exc

    tag = (release.get("tag_name") or "").lstrip("v")
    if not tag:
        raise UpdateError("Latest release has no tag_name.")
    latest_v = Version(tag)

    download_url = None
    for asset in release.get("assets", []):
        match = ASSET_RE.search(asset.get("name", ""))
        if match and Version(match.group("version")) == latest_v:
            download_url = asset.get("browser_download_url")
            break

    sha = None
    body = release.get("body") or ""
    sha_match = SHA_RE.search(body)
    if sha_match:
        sha = sha_match.group(1).lower()

    return UpdateResult(
        current_version=str(current_v),
        latest_version=str(latest_v),
        update_available=latest_v > current_v,
        download_url=download_url,
        expected_sha256=sha,
    )


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(2**16), b""):
            sha.update(chunk)
    return sha.hexdigest()


def download_update(result: UpdateResult, *, staging_dir: Path | None = None) -> Path:
    if not result.update_available or not result.download_url:
        raise UpdateError("No update to download.")

    staging_dir = staging_dir or Path(tempfile.gettempdir()) / "ordertracker-update"
    staging_dir.mkdir(parents=True, exist_ok=True)

    target = staging_dir / f"ordertracker-setup-{result.latest_version}.exe"
    logger.info("Downloading update to %s", target)
    with requests.get(result.download_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with target.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=2**16):
                if chunk:
                    fh.write(chunk)

    if result.expected_sha256:
        digest = _sha256(target)
        if digest.lower() != result.expected_sha256:
            target.unlink(missing_ok=True)
            raise UpdateError("Checksum mismatch — refusing to install update.")
    return target


def install_update(installer_path: Path, *, install_dir: Path | None = None) -> None:
    """Take a rollback snapshot, then hand control to the new installer.

    On Windows: ``ordertracker-setup-x.y.z.exe /SILENT /SUPPRESSMSGBOXES``.
    """
    install_dir = install_dir or Path(sys.argv[0]).resolve().parent
    rollback_dir = install_dir.parent / ".ordertracker-rollback"
    if rollback_dir.exists():
        shutil.rmtree(rollback_dir)
    shutil.copytree(install_dir, rollback_dir)

    logger.info("Launching installer %s", installer_path)
    if sys.platform.startswith("win"):
        os.startfile(str(installer_path))  # type: ignore[attr-defined]
    else:
        # Non-Windows path — keep deterministic behaviour for tests / dev.
        logger.warning("install_update() is a no-op on non-Windows hosts.")
