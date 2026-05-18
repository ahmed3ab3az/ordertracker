"""Settings — DB config, language, update check. Admin only."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import create_engine, text

from ...config import encrypt_database_url, load_config
from ...i18n import get_translator
from ...services.auth import SessionInfo
from ...updater.updater import UpdateError, check_for_update


class SettingsView(QWidget):
    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session
        self.t = get_translator()
        self.t.add_observer(lambda _: self._retranslate())
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        self.title = QLabel(self.t.t("settings.title"))
        self.title.setStyleSheet("font-size: 22px; font-weight: 600;")
        root.addWidget(self.title)

        # DB section
        self.db_heading = QLabel(self.t.t("settings.db.title"))
        self.db_heading.setStyleSheet("font-weight: 600; margin-top: 16px;")
        root.addWidget(self.db_heading)
        db_form = QFormLayout()
        self.db_url = QLineEdit()
        self.db_url.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_url.setPlaceholderText("postgresql+psycopg://user:pwd@host/db?sslmode=require")
        db_form.addRow("Connection URL", self.db_url)
        root.addLayout(db_form)
        db_actions = QHBoxLayout()
        db_actions.addStretch(1)
        self.test_btn = QPushButton(self.t.t("settings.db.test"))
        self.test_btn.setObjectName("secondary")
        self.test_btn.clicked.connect(self._test_db)
        self.save_btn = QPushButton(self.t.t("settings.db.save"))
        self.save_btn.clicked.connect(self._save_db)
        db_actions.addWidget(self.test_btn)
        db_actions.addWidget(self.save_btn)
        root.addLayout(db_actions)

        # Language
        self.lang_heading = QLabel(self.t.t("settings.lang"))
        self.lang_heading.setStyleSheet("font-weight: 600; margin-top: 16px;")
        root.addWidget(self.lang_heading)
        lang_row = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(self.t.t("settings.lang.en"), userData="en")
        self.lang_combo.addItem(self.t.t("settings.lang.ar"), userData="ar")
        self.lang_combo.setCurrentIndex(0 if self.t.lang == "en" else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch(1)
        root.addLayout(lang_row)

        # Updates
        self.upd_heading = QLabel(self.t.t("settings.updates.title"))
        self.upd_heading.setStyleSheet("font-weight: 600; margin-top: 16px;")
        root.addWidget(self.upd_heading)
        try:
            cfg = load_config()
            current_version = cfg.current_version
        except RuntimeError:
            current_version = "0.1.0"
        self.upd_current = QLabel(self.t.t("settings.updates.current", version=current_version))
        root.addWidget(self.upd_current)
        upd_row = QHBoxLayout()
        upd_row.addStretch(1)
        self.upd_btn = QPushButton(self.t.t("settings.updates.check"))
        self.upd_btn.clicked.connect(self._check_updates)
        upd_row.addWidget(self.upd_btn)
        root.addLayout(upd_row)

        root.addStretch(1)

    def _retranslate(self) -> None:
        self.title.setText(self.t.t("settings.title"))
        self.db_heading.setText(self.t.t("settings.db.title"))
        self.test_btn.setText(self.t.t("settings.db.test"))
        self.save_btn.setText(self.t.t("settings.db.save"))
        self.lang_heading.setText(self.t.t("settings.lang"))
        self.upd_heading.setText(self.t.t("settings.updates.title"))
        self.upd_btn.setText(self.t.t("settings.updates.check"))

    def _test_db(self) -> None:
        url = self.db_url.text().strip()
        if not url:
            return
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            QMessageBox.critical(
                self, self.t.t("common.error"), self.t.t("settings.db.error", error=str(exc))
            )
            return
        QMessageBox.information(self, self.t.t("common.confirm"), self.t.t("settings.db.ok"))

    def _save_db(self) -> None:
        url = self.db_url.text().strip()
        if not url:
            return
        try:
            encrypt_database_url(url)
        except RuntimeError as exc:
            QMessageBox.critical(self, self.t.t("common.error"), str(exc))
            return
        QMessageBox.information(
            self, self.t.t("common.save"), "Saved. Restart the app to apply the new database."
        )

    def _on_lang_changed(self, index: int) -> None:
        code = self.lang_combo.itemData(index)
        if code:
            self.t.set_language(code)

    def _check_updates(self) -> None:
        try:
            result = check_for_update()
        except UpdateError as exc:
            QMessageBox.warning(self, self.t.t("common.error"), str(exc))
            return
        if result.update_available:
            QMessageBox.information(
                self,
                self.t.t("settings.updates.title"),
                self.t.t("settings.updates.latest", version=result.latest_version),
            )
        else:
            QMessageBox.information(
                self,
                self.t.t("settings.updates.title"),
                self.t.t("settings.updates.up_to_date"),
            )
