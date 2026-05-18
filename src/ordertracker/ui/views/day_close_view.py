"""End-of-day wizard — admin closes / reopens a business day."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...constants import DayState, OrderStatus, UserRole
from ...db.models import Order
from ...db.session import db_session, transactional
from ...i18n import get_translator
from ...services.auth import SessionInfo
from ...services.days import DayService, DayValidationError


class DayCloseView(QWidget):
    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session
        self.t = get_translator()
        self.is_admin = session.role is UserRole.ADMIN
        self.t.add_observer(lambda _: self.reload())
        self._build()
        self.reload()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(self.t.t("day_close.title"))
        self.title.setStyleSheet("font-size: 22px; font-weight: 600;")
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(QLabel(self.t.t("dashboard.date")))
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(date.today())
        self.date_picker.dateChanged.connect(lambda _d: self.reload())
        header.addWidget(self.date_picker)
        root.addLayout(header)

        steps = [
            self.t.t("day_close.step1"),
            self.t.t("day_close.step2"),
            self.t.t("day_close.step3"),
            self.t.t("day_close.step4"),
        ]
        for s in steps:
            lbl = QLabel("• " + s)
            lbl.setStyleSheet("padding: 4px 0;")
            root.addWidget(lbl)

        self.summary = QTableWidget(0, 2)
        self.summary.setHorizontalHeaderLabels(["Status", "Count"])
        self.summary.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.summary, 1)

        self.state_label = QLabel()
        root.addWidget(self.state_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.close_btn = QPushButton(self.t.t("day_close.step4"))
        self.close_btn.setObjectName("large")
        self.close_btn.clicked.connect(self._close)
        self.close_btn.setEnabled(self.is_admin)
        self.reopen_btn = QPushButton(self.t.t("day_close.reopen"))
        self.reopen_btn.setObjectName("secondary")
        self.reopen_btn.clicked.connect(self._reopen)
        self.reopen_btn.setEnabled(self.is_admin)
        actions.addWidget(self.reopen_btn)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

    def reload(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        counts = {st: 0 for st in OrderStatus}
        with db_session() as s:
            for order in s.query(Order).filter(Order.date == on_date, Order.is_deleted.is_(False)).all():
                counts[order.status] += 1
            state = DayService(s).state(on_date)

        self.summary.setRowCount(len(counts))
        for r, (st, count) in enumerate(counts.items()):
            self.summary.setItem(r, 0, QTableWidgetItem(self.t.t(f"status.{st.value}")))
            item = QTableWidgetItem(str(count))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary.setItem(r, 1, item)

        self.state_label.setText(f"Day state: {state.value}")
        self.close_btn.setEnabled(self.is_admin and state == DayState.OPEN)
        self.reopen_btn.setEnabled(self.is_admin and state in (DayState.CLOSED, DayState.REOPENED))

    def _close(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        confirmed = QMessageBox.question(
            self, self.t.t("day_close.title"), self.t.t("day_close.confirm", date=on_date.isoformat())
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            with transactional() as s:
                DayService(s).close(on_date=on_date, actor_user_id=self.session.user_id)
        except DayValidationError as exc:
            QMessageBox.warning(self, self.t.t("common.error"), str(exc))
            return
        QMessageBox.information(self, self.t.t("day_close.title"), self.t.t("day_close.success"))
        self.reload()

    def _reopen(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        confirmed = QMessageBox.question(
            self,
            self.t.t("day_close.reopen"),
            self.t.t("day_close.reopen_confirm", date=on_date.isoformat()),
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            with transactional() as s:
                DayService(s).reopen(on_date=on_date, actor_user_id=self.session.user_id)
        except DayValidationError as exc:
            QMessageBox.warning(self, self.t.t("common.error"), str(exc))
        self.reload()
