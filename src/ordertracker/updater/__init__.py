"""Auto-update package."""

from .updater import UpdateError, UpdateResult, check_for_update, download_update, install_update

__all__ = ["UpdateError", "UpdateResult", "check_for_update", "download_update", "install_update"]
