"""Orders screen — scanner-friendly. Lists today's orders, supports import + status transitions."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...constants import OrderStatus
from ...db.models import ImportingCompany, ProductionCompany
from ...db.session import db_session, transactional
from ...i18n import get_translator
from ...services.auth import SessionInfo
from ...services.excel_import import parse_excel
from ...services.orders import (
    ConcurrentEditError,
    DayLockedError,
    InvalidTransitionError,
    OrderService,
)

STATUS_COLUMNS = [
    "orders.column.order_key",
    "orders.column.name",
    "orders.column.address",
    "orders.column.price",
    "orders.column.status",
    "orders.column.pc",
    "orders.column.ic",
    "orders.column.print_count",
]


class OrdersView(QWidget):
    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session
        self.t = get_translator()
        self.t.add_observer(lambda _: self._retranslate())
        self._build()
        self.reload()

    # ---------------------------------------------------------------- UI
    def _build(self) -> None:
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        self.title = QLabel(self.t.t("orders.title"))
        self.title.setStyleSheet("font-size: 22px; font-weight: 600;")
        header.addWidget(self.title)
        header.addStretch(1)

        header.addWidget(QLabel(self.t.t("dashboard.date")))
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(date.today())
        self.date_picker.dateChanged.connect(lambda _d: self.reload())
        header.addWidget(self.date_picker)

        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText(self.t.t("orders.scan_barcode"))
        self.scan_input.returnPressed.connect(self._handle_scan)
        header.addWidget(self.scan_input, 1)

        self.import_btn = QPushButton(self.t.t("orders.import_excel"))
        self.import_btn.clicked.connect(self._open_import_dialog)
        header.addWidget(self.import_btn)
        root.addLayout(header)

        self.table = QTableWidget(0, len(STATUS_COLUMNS))
        self.table.setHorizontalHeaderLabels([self.t.t(k) for k in STATUS_COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._refresh_action_state)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.assign_combo = QComboBox()
        self.assign_combo.setMinimumWidth(180)
        self.assign_btn = QPushButton(self.t.t("orders.assign_ic"))
        self.assign_btn.clicked.connect(self._assign_ic)
        actions.addWidget(self.assign_combo)
        actions.addWidget(self.assign_btn)
        actions.addStretch(1)

        self.deliver_btn = QPushButton(self.t.t("orders.mark_delivered"))
        self.deliver_btn.setObjectName("large")
        self.deliver_btn.clicked.connect(lambda: self._set_status(OrderStatus.DELIVERED))
        self.return_btn = QPushButton(self.t.t("orders.mark_returned"))
        self.return_btn.setObjectName("danger")
        self.return_btn.clicked.connect(lambda: self._set_status(OrderStatus.RETURNED))
        self.postpone_btn = QPushButton(self.t.t("orders.mark_postponed"))
        self.postpone_btn.setObjectName("secondary")
        self.postpone_btn.clicked.connect(lambda: self._set_status(OrderStatus.POSTPONED))
        self.reprint_btn = QPushButton(self.t.t("orders.reprint"))
        self.reprint_btn.setObjectName("secondary")
        self.reprint_btn.clicked.connect(self._reprint)

        actions.addWidget(self.deliver_btn)
        actions.addWidget(self.return_btn)
        actions.addWidget(self.postpone_btn)
        actions.addWidget(self.reprint_btn)
        root.addLayout(actions)

    # ---------------------------------------------------------------- DATA
    def reload(self) -> None:
        on_date = self.date_picker.date().toPyDate()
        with db_session() as s:
            service = OrderService(s)
            orders = service.list_for_date(on_date=on_date)
            ics = s.query(ImportingCompany).filter(ImportingCompany.is_deleted.is_(False)).all()
            pcs = {pc.pc_id: pc.name for pc in s.query(ProductionCompany).all()}
            ic_names = {ic.ic_id: ic.name for ic in ics}

            self._rows_meta = []
            self.table.setRowCount(len(orders))
            for r, order in enumerate(orders):
                self._rows_meta.append((order.order_id, order.updated_at, order.status))
                cells = [
                    order.order_key,
                    order.name,
                    order.address,
                    f"{order.price} EGP",
                    self.t.t(f"status.{order.status.value}"),
                    pcs.get(order.production_company_id, "?"),
                    ic_names.get(order.importing_company_id, "—") if order.importing_company_id else "—",
                    str(order.print_count),
                ]
                for c, value in enumerate(cells):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, c, item)

            self.assign_combo.clear()
            for ic in ics:
                self.assign_combo.addItem(ic.name, userData=ic.ic_id)

        self._refresh_action_state()

    def _retranslate(self) -> None:
        self.title.setText(self.t.t("orders.title"))
        self.scan_input.setPlaceholderText(self.t.t("orders.scan_barcode"))
        self.import_btn.setText(self.t.t("orders.import_excel"))
        self.assign_btn.setText(self.t.t("orders.assign_ic"))
        self.deliver_btn.setText(self.t.t("orders.mark_delivered"))
        self.return_btn.setText(self.t.t("orders.mark_returned"))
        self.postpone_btn.setText(self.t.t("orders.mark_postponed"))
        self.reprint_btn.setText(self.t.t("orders.reprint"))
        self.table.setHorizontalHeaderLabels([self.t.t(k) for k in STATUS_COLUMNS])
        self.reload()

    # ---------------------------------------------------------------- ACTIONS
    def _selected(self) -> tuple[uuid.UUID, datetime, OrderStatus] | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._rows_meta[rows[0].row()]

    def _refresh_action_state(self) -> None:
        meta = self._selected()
        active = meta is not None
        for btn in (self.deliver_btn, self.return_btn, self.postpone_btn, self.reprint_btn):
            btn.setEnabled(active)
        if not active:
            self.assign_btn.setEnabled(False)
            return
        _, _, status = meta
        self.assign_btn.setEnabled(status is OrderStatus.NEW)

    def _handle_scan(self) -> None:
        key = self.scan_input.text().strip()
        if not key:
            return
        self.scan_input.clear()
        with db_session() as s:
            order = OrderService(s).by_key(key)
        if order is None:
            QMessageBox.warning(self, self.t.t("common.error"), f"Order not found: {key}")
            return
        # Move date picker to that order's date and select.
        self.date_picker.setDate(order.date)
        self.reload()
        for row, meta in enumerate(self._rows_meta):
            if meta[0] == order.order_id:
                self.table.selectRow(row)
                break

    def _assign_ic(self) -> None:
        meta = self._selected()
        if meta is None:
            return
        order_id, updated_at, _ = meta
        ic_id = self.assign_combo.currentData()
        if ic_id is None:
            return
        try:
            with transactional() as s:
                OrderService(s).assign_ic(
                    order_id=order_id,
                    ic_id=int(ic_id),
                    expected_updated_at=updated_at,
                    actor_user_id=self.session.user_id,
                )
        except (DayLockedError, InvalidTransitionError, ConcurrentEditError) as exc:
            QMessageBox.warning(self, self.t.t("common.error"), str(exc))
        finally:
            self.reload()

    def _set_status(self, new_status: OrderStatus) -> None:
        meta = self._selected()
        if meta is None:
            return
        order_id, updated_at, _ = meta
        try:
            with transactional() as s:
                OrderService(s).transition(
                    order_id=order_id,
                    new_status=new_status,
                    expected_updated_at=updated_at,
                    actor_user_id=self.session.user_id,
                )
        except DayLockedError:
            QMessageBox.warning(self, self.t.t("common.error"), self.t.t("orders.error.day_locked"))
        except InvalidTransitionError:
            QMessageBox.warning(self, self.t.t("common.error"), self.t.t("orders.error.transition"))
        except ConcurrentEditError:
            QMessageBox.warning(self, self.t.t("common.error"), self.t.t("orders.error.concurrent"))
        finally:
            self.reload()

    def _reprint(self) -> None:
        meta = self._selected()
        if meta is None:
            return
        order_id, _, _ = meta
        # We don't print physically here — UI hands off to OS print dialog in real usage.
        from ...services.barcode import record_print, render_slip_payload  # local import

        try:
            with transactional() as s:
                order = record_print(s, order_id=order_id, actor_user_id=self.session.user_id)
                payload = render_slip_payload(order, is_reprint=order.print_count > 1)
        except ValueError as exc:
            QMessageBox.warning(self, self.t.t("common.error"), str(exc))
            return
        QMessageBox.information(
            self,
            self.t.t("orders.reprint"),
            f"{payload['order_key']} — reprint #{order.print_count}",
        )

    # ---------------------------------------------------------------- IMPORT
    def _open_import_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.t.t("orders.import_excel"), "", "Excel (*.xlsx *.xlsm)"
        )
        if not path:
            return
        preview = parse_excel(Path(path))
        if not preview.ok:
            errs = "\n".join(
                self.t.t("import.error.row", row=e.row_number, column=e.column, reason=e.reason)
                for e in preview.errors[:20]
            )
            QMessageBox.critical(
                self, self.t.t("import.errors", count=len(preview.errors)), errs
            )
            return

        # Choose PC.
        with db_session() as s:
            pcs = s.query(ProductionCompany).filter(ProductionCompany.is_deleted.is_(False)).all()
        if not pcs:
            QMessageBox.warning(self, self.t.t("common.error"), "No production companies configured.")
            return
        from PyQt6.QtWidgets import QInputDialog
        options = [pc.name for pc in pcs]
        name, ok = QInputDialog.getItem(
            self, self.t.t("import.select_pc"), self.t.t("import.select_pc"), options, 0, False
        )
        if not ok:
            return
        pc_id = next(pc.pc_id for pc in pcs if pc.name == name)

        confirmed = QMessageBox.question(
            self,
            self.t.t("import.title"),
            self.t.t("import.confirm", count=len(preview.rows)),
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        try:
            with transactional() as s:
                OrderService(s).import_bulk(
                    rows=preview.rows,
                    production_company_id=pc_id,
                    on_date=self.date_picker.date().toPyDate(),
                    actor_user_id=self.session.user_id,
                )
        except Exception as exc:
            QMessageBox.critical(self, self.t.t("common.error"), str(exc))
        finally:
            self.reload()
