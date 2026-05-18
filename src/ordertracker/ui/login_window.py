"""Login dialog. Calls :func:`services.auth.authenticate` and surfaces errors."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..db.session import transactional
from ..i18n import get_translator
from ..services.auth import (
    AccountInactive,
    AccountLocked,
    InvalidCredentials,
    SessionInfo,
    authenticate,
)


class LoginWindow(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.t = get_translator()
        self.setWindowTitle(self.t.t("login.title"))
        self.setFixedSize(360, 220)
        self._session: SessionInfo | None = None

        outer = QVBoxLayout(self)
        title = QLabel(self.t.t("app.title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 600; margin: 8px 0;")
        outer.addWidget(title)

        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(self.t.t("login.username"), self.username)
        form.addRow(self.t.t("login.password"), self.password)
        outer.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        submit = QPushButton(self.t.t("login.submit"))
        submit.setObjectName("large")
        submit.clicked.connect(self._submit)
        actions.addWidget(submit)
        outer.addLayout(actions)

        self.username.setFocus()

    def session(self) -> SessionInfo | None:
        return self._session

    def _submit(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            return
        try:
            with transactional() as s:
                self._session = authenticate(s, username, password)
        except AccountLocked:
            QMessageBox.warning(self, self.t.t("common.error"), self.t.t("login.error.locked"))
        except AccountInactive:
            QMessageBox.warning(self, self.t.t("common.error"), self.t.t("login.error.inactive"))
        except InvalidCredentials:
            QMessageBox.warning(self, self.t.t("common.error"), self.t.t("login.error.invalid"))
        else:
            self.accept()
