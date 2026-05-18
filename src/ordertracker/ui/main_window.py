"""Top-level main window with a sidebar + stacked content area."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from ..constants import SESSION_TIMEOUT_MINUTES, UserRole
from ..i18n import get_translator
from ..services.auth import SessionInfo
from .views.companies_view import ImportingCompaniesView, ProductionCompaniesView
from .views.dashboard_view import DashboardView
from .views.day_close_view import DayCloseView
from .views.orders_view import OrdersView
from .views.partners_view import PartnersView
from .views.settings_view import SettingsView
from .views.shares_view import SharesView


class MainWindow(QMainWindow):
    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session
        self.t = get_translator()
        self.setMinimumSize(QSize(1280, 800))
        self.setWindowTitle(f"{self.t.t('app.title')} — {session.username}")

        self._build_ui()
        self._wire_idle_timer()
        self.t.add_observer(self._on_language_changed)
        self._apply_layout_direction()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.menu = QListWidget()
        self.menu.setFixedWidth(220)
        self.menu.currentRowChanged.connect(self._on_menu_changed)

        self.stack = QStackedWidget()
        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)

        self.dashboard = DashboardView()
        self.orders = OrdersView(self.session)
        self.production = ProductionCompaniesView(self.session)
        self.importing = ImportingCompaniesView(self.session)
        self.partners = PartnersView(self.session)
        self.shares = SharesView(self.session)
        self.day_close = DayCloseView(self.session)
        self.settings_view = SettingsView(self.session)

        self._add_view(self.dashboard, "menu.dashboard")
        self._add_view(self.orders, "menu.orders")
        self._add_view(self.production, "menu.production_companies")
        self._add_view(self.importing, "menu.importing_companies")
        self._add_view(self.partners, "menu.partners")
        self._add_view(self.shares, "menu.daily_shares")
        self._add_view(self.day_close, "menu.day_close")
        self._add_view(self.settings_view, "menu.settings")

        if self.session.role is not UserRole.ADMIN:
            self.menu.item(7).setHidden(True)  # hide settings for non-admins

        self.menu.setCurrentRow(0)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self._refresh_status()
        self._build_menus()

    def _add_view(self, widget: QWidget, label_key: str) -> None:
        item = QListWidgetItem(self.t.t(label_key))
        item.setData(Qt.ItemDataRole.UserRole, label_key)
        self.menu.addItem(item)
        self.stack.addWidget(widget)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        lang_menu = mb.addMenu(self.t.t("menu.language"))
        for code, key in (("en", "settings.lang.en"), ("ar", "settings.lang.ar")):
            action = QAction(self.t.t(key), self)
            action.triggered.connect(lambda _checked=False, c=code: self.t.set_language(c))
            lang_menu.addAction(action)

        logout = QAction(self.t.t("menu.logout"), self)
        logout.triggered.connect(self._logout)
        mb.addAction(logout)

    # ------------------------------------------------------------------ FLOW
    def _on_menu_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        widget = self.stack.currentWidget()
        if hasattr(widget, "reload"):
            widget.reload()

    def _logout(self) -> None:
        confirmed = QMessageBox.question(
            self,
            self.t.t("menu.logout"),
            self.t.t("menu.logout") + "?",
        )
        if confirmed == QMessageBox.StandardButton.Yes:
            self.close()

    # ------------------------------------------------------------------ IDLE
    def _wire_idle_timer(self) -> None:
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(60_000)  # check every minute
        self._idle_timer.timeout.connect(self._check_idle)
        self._idle_timer.start()

    def _check_idle(self) -> None:
        if self.session.expired():
            QMessageBox.warning(self, self.t.t("app.title"), "Session timed out. Please log in again.")
            self.close()

    # ------------------------------------------------------------------ I18N
    def _on_language_changed(self, _code: str) -> None:
        # Rebuild labels.
        for i in range(self.menu.count()):
            item = self.menu.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self.t.t(key))
        self.menuBar().clear()
        self._build_menus()
        self._apply_layout_direction()

    def _apply_layout_direction(self) -> None:
        if self.t.is_rtl:
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    # ------------------------------------------------------------------ STATUS
    def _refresh_status(self) -> None:
        text = f"{self.session.username} · {self.session.role.value} · {SESSION_TIMEOUT_MINUTES} min timeout"
        self.statusBar().showMessage(text)

    # ------------------------------------------------------------------ ACTIVITY
    def event(self, event) -> bool:
        self.session.touch()
        return super().event(event)
