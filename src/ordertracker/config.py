"""Configuration loader.

Credentials are encrypted at rest using Fernet and stored under the OS keyring.
Non-secret settings live in environment variables (loaded from ``.env`` in dev).

The pattern is:

* The DB URL itself is treated as a secret.
* A symmetric Fernet key is generated on first run and stored under the OS
  keyring (service name: ``ordertracker``).
* The encrypted DB URL is also stored under that keyring entry.
* When the app boots it pulls + decrypts the URL with the key, falling back
  to ``DATABASE_URL`` from the environment for development convenience.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

try:  # Optional in dev; required in production
    import keyring
except Exception:
    keyring = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "ordertracker"
KEYRING_FERNET_KEY = "fernet_key"
KEYRING_DB_URL_ENCRYPTED = "database_url_encrypted"
KEYRING_RELEASES_REPO = "releases_repo"


@dataclass(frozen=True)
class AppConfig:
    """In-memory representation of the configuration."""

    database_url: str
    env: str = "production"
    log_level: str = "INFO"
    default_lang: str = "en"
    releases_repo: str = "ahmed3ab3az/ordertracker"
    current_version: str = "0.1.0"
    app_data_dir: Path = field(default_factory=lambda: Path.home() / ".ordertracker")
    archive_dir: Path = field(default_factory=lambda: Path.home() / ".ordertracker" / "archives")

    def ensure_dirs(self) -> None:
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)


def _get_or_create_fernet_key() -> bytes:
    if keyring is None:  # dev fallback — store next to .env
        local_key_path = Path.cwd() / ".fernet_key"
        if local_key_path.exists():
            return local_key_path.read_bytes()
        key = Fernet.generate_key()
        local_key_path.write_bytes(key)
        local_key_path.chmod(0o600)
        return key

    stored = keyring.get_password(KEYRING_SERVICE, KEYRING_FERNET_KEY)
    if stored:
        return stored.encode("utf-8")
    new_key = Fernet.generate_key()
    keyring.set_password(KEYRING_SERVICE, KEYRING_FERNET_KEY, new_key.decode("utf-8"))
    return new_key


def encrypt_database_url(url: str) -> None:
    """Encrypt + persist the DB URL in the OS keyring."""
    fernet = Fernet(_get_or_create_fernet_key())
    token = fernet.encrypt(url.encode("utf-8")).decode("utf-8")
    if keyring is None:
        raise RuntimeError("Keyring not available; cannot persist DB URL securely.")
    keyring.set_password(KEYRING_SERVICE, KEYRING_DB_URL_ENCRYPTED, token)


def _decrypt_database_url() -> str | None:
    if keyring is None:
        return None
    token = keyring.get_password(KEYRING_SERVICE, KEYRING_DB_URL_ENCRYPTED)
    if not token:
        return None
    try:
        fernet = Fernet(_get_or_create_fernet_key())
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("Stored DB URL token is invalid; falling back to env vars.")
        return None


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def load_config() -> AppConfig:
    """Build the :class:`AppConfig` from keyring + environment."""
    _load_dotenv(Path.cwd() / ".env")

    database_url = _decrypt_database_url() or os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it via the Settings dialog (recommended) or DATABASE_URL env var (dev only)."
        )

    cfg = AppConfig(
        database_url=database_url,
        env=os.environ.get("ORDERTRACKER_ENV", "production"),
        log_level=os.environ.get("ORDERTRACKER_LOG_LEVEL", "INFO"),
        default_lang=os.environ.get("ORDERTRACKER_DEFAULT_LANG", "en"),
        releases_repo=os.environ.get("ORDERTRACKER_RELEASES_REPO", "ahmed3ab3az/ordertracker"),
        current_version=os.environ.get("ORDERTRACKER_CURRENT_VERSION", "0.1.0"),
    )
    cfg.ensure_dirs()
    return cfg
