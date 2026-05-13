"""Small compatibility layer around PySide6-Fluent-Widgets.

The v3 UI uses Fluent Widgets when the dependency is installed. The fallback
classes keep the module importable in plain PySide6 environments during early
development and automated syntax checks.
"""

from __future__ import annotations

import textwrap

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    import qfluentwidgets as _fluent
except Exception:  # pragma: no cover - exercised only when Fluent Widgets is absent.
    _fluent = None


class _FallbackTheme:
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class _FallbackNavigationItemPosition:
    TOP = "top"
    BOTTOM = "bottom"


class _FallbackIcon:
    """Return empty Qt icons for FluentIcon names in fallback mode."""

    def __getattr__(self, _name):
        return QIcon()


class _FallbackCardWidget(QFrame):
    """Minimal CardWidget replacement for environments without qfluentwidgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FallbackCardWidget")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame#FallbackCardWidget {
                background: #202225;
                border: 1px solid #343842;
                border-radius: 8px;
            }
            """
        )


class _FallbackNavigationInterface(QWidget):
    """Simple vertical navigation used when Fluent Widgets are unavailable."""

    def __init__(self, parent=None, *_, **__):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)

    def addItem(self, routeKey, icon, text, onClick, position=None, tooltip=None, **_kwargs):
        button = QPushButton(text, self)
        button.setObjectName(str(routeKey))
        button.setToolTip(tooltip or text)
        button.clicked.connect(onClick)
        if position == _FallbackNavigationItemPosition.BOTTOM:
            self._layout.addWidget(button)
        else:
            self._layout.insertWidget(max(0, self._layout.count() - 1), button)
        return button


def _fallback_set_theme(_theme):
    return None


def _fallback_is_dark_theme():
    return False


Theme = getattr(_fluent, "Theme", _FallbackTheme)
NavigationItemPosition = getattr(_fluent, "NavigationItemPosition", _FallbackNavigationItemPosition)
FIF = getattr(_fluent, "FluentIcon", _FallbackIcon())
CardWidget = getattr(_fluent, "CardWidget", getattr(_fluent, "SimpleCardWidget", _FallbackCardWidget)) if _fluent else _FallbackCardWidget
NavigationInterface = getattr(_fluent, "NavigationInterface", _FallbackNavigationInterface) if _fluent else _FallbackNavigationInterface
PushButton = getattr(_fluent, "PushButton", QPushButton) if _fluent else QPushButton
PrimaryPushButton = getattr(_fluent, "PrimaryPushButton", QPushButton) if _fluent else QPushButton
ToolButton = getattr(_fluent, "ToolButton", QToolButton) if _fluent else QToolButton
LineEdit = getattr(_fluent, "LineEdit", QLineEdit) if _fluent else QLineEdit
TextEdit = getattr(_fluent, "TextEdit", QTextEdit) if _fluent else QTextEdit
BodyLabel = getattr(_fluent, "BodyLabel", QLabel) if _fluent else QLabel
CaptionLabel = getattr(_fluent, "CaptionLabel", QLabel) if _fluent else QLabel
SubtitleLabel = getattr(_fluent, "SubtitleLabel", QLabel) if _fluent else QLabel
setTheme = getattr(_fluent, "setTheme", _fallback_set_theme) if _fluent else _fallback_set_theme
isDarkTheme = getattr(_fluent, "isDarkTheme", _fallback_is_dark_theme) if _fluent else _fallback_is_dark_theme


def fluent_icon(name: str) -> QIcon:
    """Return a Fluent icon by attribute name, or an empty icon in fallback mode."""
    return getattr(FIF, name, QIcon())


def make_card_layout(card: QWidget) -> QVBoxLayout:
    """Create the standard 8px-grid layout used by v3 cards."""
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(5)
    return layout


def add_info_header(layout: QVBoxLayout, title: str, message: str) -> QPushButton:
    """Add a compact card title row with an explanatory info button."""
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)

    row_layout.addWidget(BodyLabel(title))
    row_layout.addStretch(1)

    button = QPushButton("i")
    button.setObjectName("V3InfoButton")
    button.setFixedSize(22, 22)
    wrapped_message = compact_tooltip(message)
    button.setToolTip(wrapped_message)
    button.setStatusTip(wrapped_message)
    button.setWhatsThis(wrapped_message)
    button.setAccessibleName(f"About {title}")
    row_layout.addWidget(button)

    layout.addWidget(row)
    return button


def compact_tooltip(message: str, width: int = 58) -> str:
    """Return a compact multiline tooltip string for long explanatory text."""
    paragraphs = [part.strip() for part in str(message).splitlines() if part.strip()]
    if not paragraphs:
        return ""
    return "\n".join(textwrap.fill(paragraph, width=width) for paragraph in paragraphs)


def mark_primary_action(button: QPushButton) -> QPushButton:
    """Mark a command button as the orange primary action used by v3."""
    button.setObjectName("V3PrimaryButton")
    button.setProperty("primaryAction", True)
    button.setStyleSheet(
        """
        QPushButton {
            background-color: #f28c28;
            border: 1px solid #b85f00;
            color: #241100;
            font-weight: 700;
            border-radius: 9px;
            padding: 4px 8px;
        }
        QPushButton:hover {
            background-color: #ff9f3d;
            border-color: #cf7000;
        }
        QPushButton:disabled {
            background-color: #ead8c4;
            border-color: #d8c1a4;
            color: #8b7760;
        }
        """
    )
    return button


def apply_v3_palette(widget: QWidget) -> None:
    """Apply the light v3 workbench style used by the modern GUI."""
    widget.setStyleSheet(
        """
        QWidget {
            color: #18202b;
            background: #eef3f6;
            font-family: "Segoe UI Variable", "Aptos", "Segoe UI";
            font-size: 8.5pt;
        }
        QWidget#V3Root {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #f9fbfc,
                stop: 0.52 #edf4f7,
                stop: 1 #e4edf2
            );
        }
        QWidget#V3NavigationSidebar {
            background: #f7fafb;
            border-right: 1px solid #d7e0e7;
        }
        QScrollArea {
            background: transparent;
            border: none;
        }
        QScrollArea > QWidget > QWidget {
            background: transparent;
        }
        QFrame {
            border-radius: 14px;
        }
        QFrame#V3StatusBar {
            background: #f8fbfc;
            border-top: 1px solid #d7e0e7;
        }
        QFrame#FallbackCardWidget,
        CardWidget,
        SimpleCardWidget {
            background: #ffffff;
            border: 1px solid #d8e2e8;
            border-radius: 16px;
        }
        QGroupBox#V3ValveGroup {
            background: #f8fbfc;
            border: 1px solid #d8e2e8;
            border-radius: 10px;
            margin-top: 8px;
            padding-top: 6px;
            font-weight: 600;
        }
        QGroupBox#V3ValveGroup::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: #344652;
            background: #ffffff;
        }
        QWidget#V3PlotPanel {
            background: #f8fbfc;
            border-left: 1px solid #d7e0e7;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QListWidget {
            background: #ffffff;
            color: #18202b;
            border: 1px solid #cbd7df;
            border-radius: 8px;
            padding: 4px;
            selection-background-color: #2d7d9a;
            selection-color: #ffffff;
        }
        QPushButton {
            background: #ffffff;
            color: #18202b;
            border: 1px solid #bfd0da;
            border-radius: 9px;
            padding: 4px 8px;
        }
        QPushButton:hover {
            background: #edf7fb;
            border-color: #7eb4ca;
        }
        QPushButton#V3PrimaryButton,
        QPushButton[primaryAction="true"],
        PrimaryPushButton {
            background: #f28c28;
            border: 1px solid #b85f00;
            color: #241100;
            font-weight: 700;
        }
        QPushButton#V3PrimaryButton:hover,
        QPushButton[primaryAction="true"]:hover,
        PrimaryPushButton:hover {
            background: #ff9f3d;
            border-color: #cf7000;
        }
        QPushButton#V3PrimaryButton:disabled,
        QPushButton[primaryAction="true"]:disabled,
        PrimaryPushButton:disabled {
            background: #ead8c4;
            border-color: #d8c1a4;
            color: #8b7760;
        }
        QPushButton:checked {
            background: #d7f0e5;
            border-color: #43a775;
            color: #0e5131;
        }
        QPushButton#V3ValveButton[valveActive="true"] {
            background: #008f7a;
            border: 1px solid #006b5c;
            color: #ffffff;
            font-weight: 700;
        }
        QPushButton#V3ValveButton[valveActive="true"]:hover {
            background: #00a88f;
            border-color: #007a69;
        }
        QPushButton#V3ValveButton[valveActive="true"]:disabled {
            background: #8abdb4;
            border-color: #76a89f;
            color: #f8ffff;
        }
        QPushButton#V3ValveButton[valveGroup="pneumatic"][valveActive="true"] {
            background: #1f6fbe;
            border: 1px solid #174f88;
            color: #ffffff;
            font-weight: 700;
        }
        QPushButton#V3ValveButton[valveGroup="pneumatic"][valveActive="true"]:hover {
            background: #2d82d8;
            border-color: #1b5f9f;
        }
        QPushButton#V3ValveButton[valveGroup="fluidic"][valveActive="true"] {
            background: #009b72;
            border: 1px solid #00785a;
            color: #ffffff;
            font-weight: 700;
        }
        QPushButton#V3ValveButton[valveGroup="fluidic"][valveActive="true"]:hover {
            background: #00b383;
            border-color: #008866;
        }
        QPushButton#V3InfoButton {
            min-width: 22px;
            max-width: 22px;
            min-height: 22px;
            max-height: 22px;
            padding: 0;
            border-radius: 11px;
            background: #e7f2f7;
            border: 1px solid #8cb9cc;
            color: #1b5d78;
            font-weight: 700;
        }
        QPushButton#V3InfoButton:hover {
            background: #d6edf6;
            border-color: #5a9fbb;
        }
        QPushButton:disabled,
        QLineEdit:disabled,
        QSpinBox:disabled,
        QDoubleSpinBox:disabled {
            color: #80909a;
            background: #eef2f4;
            border-color: #d7e0e7;
        }
        QLabel#V3MetricValue {
            font-size: 8.5pt;
            font-weight: 600;
            color: #0b5c78;
        }
        QLabel#V3MetricCaption {
            color: #344652;
            font-size: 8pt;
        }
        """
    )


apply_dark_palette = apply_v3_palette


def stretch_row(*widgets: QWidget) -> QWidget:
    """Return a compact row widget for card controls."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return row
