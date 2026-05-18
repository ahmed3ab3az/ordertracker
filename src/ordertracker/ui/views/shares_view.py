"""Daily partner shares — capital inputs per partner per day."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...db.session import db_session, transactional
from ...i18n import get_translator
from ...services.auth import SessionInfo
from ...services.partners import DailyPartnerShareService, PartnerService


class SharesView(QWidget):
    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session
        self.t = get_translator()
        self.t.add_observer(lambda _: self.reload())
        self._build()
        self.reload()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(self.t.t("shares.title"))
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

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [
                self.t.t("shares.column.partner"),
                self.t.t("shares.column.share"),
                self.t.t("shares.column.percentage"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.total_label = QLabel()
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.total_label)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.save_btn = QPushButton(self.t.t("common.save"))
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

    def reload(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        with db_session() as s:
            self._partners = PartnerService(s).list_active()
            shares = {sh.partner_id: sh.daily_share for sh in DailyPartnerShareService(s).list_for_date(on_date=on_date)}

        self.table.setRowCount(len(self._partners))
        self._inputs: list[QDoubleSpinBox] = []
        total = Decimal("0.00")
        for r, p in enumerate(self._partners):
            name_item = QTableWidgetItem(p.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, name_item)
            spin = QDoubleSpinBox()
            spin.setRange(0, 1_000_000)
            spin.setDecimals(2)
            current = float(shares.get(p.partner_id, Decimal("0.00")))
            spin.setValue(current)
            self.table.setCellWidget(r, 1, spin)
            self._inputs.append(spin)
            pct_item = QTableWidgetItem("0%")
            pct_item.setFlags(pct_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 2, pct_item)
            total += Decimal(str(current))

        self._update_percentages(total)
        for spin in self._inputs:
            spin.valueChanged.connect(self._recompute)

    def _recompute(self) -> None:
        total = Decimal("0.00")
        for spin in self._inputs:
            total += Decimal(str(spin.value()))
        self._update_percentages(total)

    def _update_percentages(self, total: Decimal) -> None:
        for r, spin in enumerate(self._inputs):
            value = Decimal(str(spin.value()))
            pct = (value / total * 100) if total > 0 else Decimal("0")
            cell = self.table.item(r, 2)
            if cell is not None:
                cell.setText(f"{pct:.2f}%")
        self.total_label.setText(self.t.t("shares.total", total=f"{total:.2f}"))

    def _save(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        with transactional() as s:
            svc = DailyPartnerShareService(s)
            for p, spin in zip(self._partners, self._inputs, strict=True):
                svc.upsert(
                    partner_id=p.partner_id,
                    on_date=on_date,
                    daily_share=Decimal(str(spin.value())),
                    actor_user_id=self.session.user_id,
                )
