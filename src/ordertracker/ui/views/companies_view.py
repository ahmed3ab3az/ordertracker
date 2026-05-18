"""CRUD screens for Production / Importing companies."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
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

from ...db.session import db_session, transactional
from ...i18n import get_translator
from ...services.auth import SessionInfo
from ...services.companies import (
    ImportingCompanyService,
    ProductionCompanyService,
)


class _CompanyDialog(QDialog):
    """Generic editor dialog. Subclasses define which fields show up."""

    def __init__(self, title: str, *, fields: dict[str, tuple[str, float]]) -> None:
        super().__init__()
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self._inputs: dict[str, QLineEdit | QDoubleSpinBox] = {}
        for key, (label, default) in fields.items():
            if isinstance(default, str):
                widget: QLineEdit | QDoubleSpinBox = QLineEdit()
                widget.setText(default)
            else:
                widget = QDoubleSpinBox()
                widget.setRange(0, 1_000_000)
                widget.setDecimals(2)
                widget.setValue(default)
            self._inputs[key] = widget
            layout.addRow(label, widget)

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

    def values(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, widget in self._inputs.items():
            if isinstance(widget, QLineEdit):
                out[key] = widget.text().strip()
            else:
                out[key] = Decimal(str(widget.value()))
        return out


class _CompanyView(QWidget):
    """Base class shared between PC + IC views."""

    columns: ClassVar[list[tuple[str, str]]] = []  # (key, attr_name)
    title_key: str = "menu.production_companies"

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
        self.title = QLabel(self.t.t(self.title_key))
        self.title.setStyleSheet("font-size: 22px; font-weight: 600;")
        header.addWidget(self.title)
        header.addStretch(1)
        self.add_btn = QPushButton("+")
        self.add_btn.clicked.connect(self._add)
        header.addWidget(self.add_btn)
        root.addLayout(header)

        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([self.t.t(k) for k, _ in self.columns])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("secondary")
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        actions.addStretch(1)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        root.addLayout(actions)

    # Override hooks ---------------------------------------------------
    def fetch(self) -> list[object]:  # pragma: no cover - abstract
        raise NotImplementedError

    def fields_for_dialog(self, existing: object | None) -> dict[str, tuple[str, float | str]]:  # pragma: no cover
        raise NotImplementedError

    def save(self, values: dict[str, object], existing: object | None) -> None:  # pragma: no cover
        raise NotImplementedError

    def delete(self, item: object) -> None:  # pragma: no cover
        raise NotImplementedError

    def row_values(self, item: object) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    # Common flows -----------------------------------------------------
    def reload(self) -> None:
        items = self.fetch()
        self._items = items
        self.table.setRowCount(len(items))
        for r, item in enumerate(items):
            for c, value in enumerate(self.row_values(item)):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, cell)

    def _selected(self) -> object | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._items[rows[0].row()]

    def _add(self) -> None:
        dialog = _CompanyDialog("Add", fields=self.fields_for_dialog(None))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save(dialog.values(), None)
            self.reload()

    def _edit(self) -> None:
        item = self._selected()
        if item is None:
            return
        dialog = _CompanyDialog("Edit", fields=self.fields_for_dialog(item))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.save(dialog.values(), item)
            except ValueError as exc:
                QMessageBox.warning(self, self.t.t("common.error"), str(exc))
            self.reload()

    def _delete(self) -> None:
        item = self._selected()
        if item is None:
            return
        confirmed = QMessageBox.question(
            self, "Delete", f"Delete {item.name}?"
        )
        if confirmed == QMessageBox.StandardButton.Yes:
            try:
                self.delete(item)
            except ValueError as exc:
                QMessageBox.warning(self, self.t.t("common.error"), str(exc))
            self.reload()


class ProductionCompaniesView(_CompanyView):
    title_key = "menu.production_companies"
    columns: ClassVar[list[tuple[str, str]]] = [
        ("orders.column.pc", "name"),
        ("import.select_pc", "shipping_cost"),
    ]

    def fetch(self) -> list[object]:
        with db_session() as s:
            return ProductionCompanyService(s).list_active()

    def row_values(self, item) -> list[str]:
        return [item.name, str(item.shipping_cost)]

    def fields_for_dialog(self, existing) -> dict[str, tuple[str, float | str]]:
        return {
            "name": ("Name", existing.name if existing else ""),
            "shipping_cost": ("Shipping cost (EGP)", float(existing.shipping_cost) if existing else 0.0),
        }

    def save(self, values, existing) -> None:
        with transactional() as s:
            svc = ProductionCompanyService(s)
            if existing is None:
                svc.create(
                    name=str(values["name"]),
                    shipping_cost=Decimal(str(values["shipping_cost"])),
                    actor_user_id=self.session.user_id,
                )
            else:
                svc.update(
                    pc_id=existing.pc_id,
                    name=str(values["name"]),
                    shipping_cost=Decimal(str(values["shipping_cost"])),
                    actor_user_id=self.session.user_id,
                )

    def delete(self, item) -> None:
        with transactional() as s:
            ProductionCompanyService(s).soft_delete(
                pk=item.pc_id, actor_user_id=self.session.user_id
            )


class ImportingCompaniesView(_CompanyView):
    title_key = "menu.importing_companies"
    columns: ClassVar[list[tuple[str, str]]] = [
        ("orders.column.ic", "name"),
        ("orders.column.price", "profit_per_order"),
        ("dashboard.gross_profit", "day_cost"),
    ]

    def fetch(self) -> list[object]:
        with db_session() as s:
            return ImportingCompanyService(s).list_active()

    def row_values(self, item) -> list[str]:
        return [item.name, str(item.profit_per_order), str(item.day_cost)]

    def fields_for_dialog(self, existing) -> dict[str, tuple[str, float | str]]:
        return {
            "name": ("Name", existing.name if existing else ""),
            "profit_per_order": (
                "Profit per delivered order (EGP)",
                float(existing.profit_per_order) if existing else 0.0,
            ),
            "day_cost": (
                "Day cost (EGP)",
                float(existing.day_cost) if existing else 0.0,
            ),
        }

    def save(self, values, existing) -> None:
        with transactional() as s:
            svc = ImportingCompanyService(s)
            if existing is None:
                svc.create(
                    name=str(values["name"]),
                    profit_per_order=Decimal(str(values["profit_per_order"])),
                    day_cost=Decimal(str(values["day_cost"])),
                    actor_user_id=self.session.user_id,
                )
            else:
                svc.update(
                    ic_id=existing.ic_id,
                    name=str(values["name"]),
                    profit_per_order=Decimal(str(values["profit_per_order"])),
                    day_cost=Decimal(str(values["day_cost"])),
                    actor_user_id=self.session.user_id,
                )

    def delete(self, item) -> None:
        with transactional() as s:
            ImportingCompanyService(s).soft_delete(
                pk=item.ic_id, actor_user_id=self.session.user_id
            )
