"""Application entry point — wires config + UI + DB engine."""

from __future__ import annotations

import logging
import sys
from importlib.resources import files

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from .config import load_config
from .db.session import init_engine
from .i18n import get_translator
from .ui.login_window import LoginWindow
from .ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_stylesheet() -> str:
    try:
        return (files("ordertracker.ui") / "styles" / "app.qss").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OrderTracker")

    try:
        cfg = load_config()
    except RuntimeError as exc:
        QMessageBox.critical(None, "Configuration error", str(exc))
        return 1

    _configure_logging(cfg.log_level)
    get_translator(cfg.default_lang)
    app.setStyleSheet(_load_stylesheet())
    if cfg.default_lang == "ar":
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    try:
        init_engine(cfg.database_url)
    except Exception as exc:
        QMessageBox.critical(None, "Database error", str(exc))
        return 2

    login = LoginWindow()
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0
    session = login.session()
    if session is None:
        return 0

    window = MainWindow(session)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
