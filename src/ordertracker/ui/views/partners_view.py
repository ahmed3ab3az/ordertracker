"""Partner management — only Admin sees the create/reset/delete actions."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...constants import UserRole
from ...db.session import db_session, transactional
from ...i18n import get_translator
from ...services.auth import SessionInfo
from ...services.partners import PartnerService


class _AddPartnerDialog(QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add partner")
        layout = QFormLayout(self)
        self.name = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Name", self.name)
        layout.addRow("Username", self.username)
        layout.addRow("Password", self.password)
        actions = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.clicked.connect(self.accept)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addRow(actions)


class PartnersView(QWidget):
    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session
        self.t = get_translator()
        self.t.add_observer(lambda _: self.reload())
        self.is_admin = session.role is UserRole.ADMIN
        self._build()
        self.reload()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(self.t.t("partners.title"))
        self.title.setStyleSheet("font-size: 22px; font-weight: 600;")
        header.addWidget(self.title)
        header.addStretch(1)
        self.add_btn = QPushButton(self.t.t("partners.add"))
        self.add_btn.clicked.connect(self._add)
        self.add_btn.setEnabled(self.is_admin)
        header.addWidget(self.add_btn)
        root.addLayout(header)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [
                self.t.t("partners.column.name"),
                self.t.t("partners.column.username"),
                self.t.t("partners.column.active"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.reset_btn = QPushButton(self.t.t("partners.reset_password"))
        self.reset_btn.setObjectName("secondary")
        self.reset_btn.clicked.connect(self._reset_password)
        self.delete_btn = QPushButton(self.t.t("partners.delete"))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.reset_btn.setEnabled(self.is_admin)
        self.delete_btn.setEnabled(self.is_admin)
        actions.addWidget(self.reset_btn)
        actions.addWidget(self.delete_btn)
        root.addLayout(actions)

    def reload(self) -> None:
        with db_session() as s:
            partners = PartnerService(s).list_active()
            self._items = partners
            self.table.setRowCount(len(partners))
            for r, p in enumerate(partners):
                cells = [p.name, p.user.username if p.user else "—", "Yes" if p.user and p.user.active else "No"]
                for c, value in enumerate(cells):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, c, item)

    def _selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._items[rows[0].row()]

    def _add(self) -> None:
        dialog = _AddPartnerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.name.text().strip()
        username = dialog.username.text().strip()
        password = dialog.password.text()
        if not name or not username or not password:
            return
        try:
            with transactional() as s:
                PartnerService(s).create(
                    name=name, username=username, password=password, actor_user_id=self.session.user_id
                )
        except ValueError as exc:
            QMessageBox.warning(self, self.t.t("common.error"), str(exc))
        self.reload()

    def _reset_password(self) -> None:
        partner = self._selected()
        if partner is None:
            return
        new_pw, ok = QInputDialog.getText(
            self, self.t.t("partners.reset_password"), "New password", QLineEdit.EchoMode.Password
        )
        if not ok or not new_pw:
            return
        with transactional() as s:
            PartnerService(s).reset_password(
                partner_id=partner.partner_id,
                new_password=new_pw,
                actor_user_id=self.session.user_id,
            )
        QMessageBox.information(self, self.t.t("common.confirm"), "Password updated.")

    def _delete(self) -> None:
        partner = self._selected()
        if partner is None:
            return
        confirmed = QMessageBox.question(
            self, self.t.t("partners.delete"), f"Deactivate {partner.name}?"
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        with transactional() as s:
            PartnerService(s).soft_delete(
                partner_id=partner.partner_id, actor_user_id=self.session.user_id
            )
        self.reload()
