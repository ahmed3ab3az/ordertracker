"""Dashboard — daily KPIs + per-IC delivered/returned/postponed counts."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...constants import OrderStatus
from ...db.models import ImportingCompany, Order
from ...db.session import db_session
from ...i18n import get_translator
from ...services.profit import compute_daily_profit


class StatCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setMinimumSize(180, 96)
        layout = QVBoxLayout(self)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #475569; font-size: 12px;")
        self.value_lbl = QLabel("0")
        self.value_lbl.setStyleSheet("font-size: 28px; font-weight: 600;")
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_lbl.setText(value)

    def set_title(self, value: str) -> None:
        self.title_lbl.setText(value)


class DashboardView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.t = get_translator()
        self.t.add_observer(lambda _: self.reload())
        self._build()
        self.reload()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(self.t.t("dashboard.title"))
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

        cards = QGridLayout()
        self.card_total = StatCard(self.t.t("dashboard.total_orders"))
        self.card_delivered = StatCard(self.t.t("dashboard.delivered"))
        self.card_returned = StatCard(self.t.t("dashboard.returned"))
        self.card_postponed = StatCard(self.t.t("dashboard.postponed"))
        self.card_on_hold = StatCard(self.t.t("dashboard.on_hold"))
        self.card_gross = StatCard(self.t.t("dashboard.gross_profit"))
        self.card_net = StatCard(self.t.t("dashboard.net_profit"))

        for i, card in enumerate(
            (
                self.card_total,
                self.card_delivered,
                self.card_returned,
                self.card_postponed,
                self.card_on_hold,
                self.card_gross,
                self.card_net,
            )
        ):
            cards.addWidget(card, i // 4, i % 4)

        root.addLayout(cards)

        self.ic_table = QTableWidget(0, 5)
        self.ic_table.setHorizontalHeaderLabels(
            [
                self.t.t("orders.column.ic"),
                self.t.t("dashboard.delivered"),
                self.t.t("dashboard.returned"),
                self.t.t("dashboard.postponed"),
                self.t.t("dashboard.net_profit"),
            ]
        )
        self.ic_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.ic_table, 1)

    def reload(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        with db_session() as s:
            view = compute_daily_profit(s, on_date=on_date)
            ic_rows = []
            for ic in s.query(ImportingCompany).filter(ImportingCompany.is_deleted.is_(False)).all():
                delivered = (
                    s.query(Order)
                    .filter(
                        Order.date == on_date,
                        Order.importing_company_id == ic.ic_id,
                        Order.status == OrderStatus.DELIVERED,
                        Order.is_deleted.is_(False),
                    )
                    .count()
                )
                returned = (
                    s.query(Order)
                    .filter(
                        Order.date == on_date,
                        Order.importing_company_id == ic.ic_id,
                        Order.status == OrderStatus.RETURNED,
                        Order.is_deleted.is_(False),
                    )
                    .count()
                )
                postponed = (
                    s.query(Order)
                    .filter(
                        Order.date == on_date,
                        Order.importing_company_id == ic.ic_id,
                        Order.status == OrderStatus.POSTPONED,
                        Order.is_deleted.is_(False),
                    )
                    .count()
                )
                ic_line = next((line for line in view.ic_lines if line.ic_id == ic.ic_id), None)
                net = ic_line.net_profit if ic_line else 0
                ic_rows.append((ic.name, delivered, returned, postponed, net))

        delivered_total = sum(c.num_delivered for c in view.ic_lines)
        self.card_total.set_value(str(sum(r[1] + r[2] + r[3] for r in ic_rows)))
        self.card_delivered.set_value(str(delivered_total))
        self.card_returned.set_value(str(sum(r[2] for r in ic_rows)))
        self.card_postponed.set_value(str(sum(r[3] for r in ic_rows)))
        self.card_on_hold.set_value(
            str(
                sum(
                    1
                    for _ in []  # placeholder to keep type consistent; populated by services if needed
                )
            )
        )
        self.card_gross.set_value(
            str(sum(line.gross_profit for line in view.ic_lines)) + " EGP"
        )
        self.card_net.set_value(f"{view.total_net_profit} EGP")

        self.ic_table.setRowCount(len(ic_rows))
        for row, (name, d, r, p, n) in enumerate(ic_rows):
            for col, value in enumerate((name, d, r, p, f"{n} EGP")):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.ic_table.setItem(row, col, cell)
