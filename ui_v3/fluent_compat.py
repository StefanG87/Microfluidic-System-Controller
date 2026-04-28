"""Small compatibility layer around PySide6-Fluent-Widgets.

The v3 UI uses Fluent Widgets when the dependency is installed. The fallback
classes keep the module importable in plain PySide6 environments during early
development and automated syntax checks.
"""

from __future__ import annotations

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
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)
    return layout


def apply_v3_palette(widget: QWidget) -> None:
    """Apply the light v3 workbench style used by the modern GUI."""
    widget.setStyleSheet(
        """
        QWidget {
            color: #18202b;
            background: #eef3f6;
            font-family: "Segoe UI Variable", "Aptos", "Segoe UI";
            font-size: 10pt;
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
        QWidget#V3PlotPanel {
            background: #f8fbfc;
            border-left: 1px solid #d7e0e7;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QListWidget {
            background: #ffffff;
            color: #18202b;
            border: 1px solid #cbd7df;
            border-radius: 8px;
            padding: 6px;
            selection-background-color: #2d7d9a;
            selection-color: #ffffff;
        }
        QPushButton {
            background: #ffffff;
            color: #18202b;
            border: 1px solid #bfd0da;
            border-radius: 9px;
            padding: 7px 12px;
        }
        QPushButton:hover {
            background: #edf7fb;
            border-color: #7eb4ca;
        }
        QPushButton:checked {
            background: #d7f0e5;
            border-color: #43a775;
            color: #0e5131;
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
            font-size: 18pt;
            font-weight: 650;
            color: #0b5c78;
        }
        QLabel#V3MetricCaption {
            color: #60717d;
            font-size: 9pt;
        }
        """
    )


apply_dark_palette = apply_v3_palette


def stretch_row(*widgets: QWidget) -> QWidget:
    """Return a compact row widget for card controls."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return row
