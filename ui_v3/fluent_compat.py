"""Small compatibility layer around PySide6-Fluent-Widgets.

The v3 UI uses Fluent Widgets when the dependency is installed. The fallback
classes keep the module importable in plain PySide6 environments during early
development and automated syntax checks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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
    return True


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


def apply_dark_palette(widget: QWidget) -> None:
    """Apply a restrained dark stylesheet for fallback and app-specific surfaces."""
    widget.setStyleSheet(
        """
        QWidget {
            color: #f3f5f7;
            background: #111316;
            font-size: 10pt;
        }
        QFrame {
            border-radius: 8px;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QListWidget {
            background: #1b1e23;
            color: #f3f5f7;
            border: 1px solid #343842;
            border-radius: 6px;
            padding: 4px;
        }
        QPushButton {
            background: #262b33;
            border: 1px solid #3a414d;
            border-radius: 6px;
            padding: 6px 10px;
        }
        QPushButton:hover {
            background: #303744;
        }
        QPushButton:checked {
            background: #0f6cbd;
            border-color: #3b9cff;
        }
        """
    )


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
