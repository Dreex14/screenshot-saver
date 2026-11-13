"""Tema oscuro estilo Windows 11 e icono de la aplicación."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication

BACKGROUND = "#202020"
SURFACE = "#2b2b2b"
BORDER = "#3a3a3a"
TEXT = "#ffffff"
MUTED = "#a3a3a3"
ACCENT = "#60cdff"
SUCCESS = "#6ccb5f"
ERROR = "#ff99a4"
IDLE = "#8a8a8a"

_STYLESHEET = f"""
QLabel#sectionTitle {{
    color: {MUTED};
    font-size: 8pt;
    font-weight: 600;
}}
QLabel#pathField {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QLineEdit {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-bottom: 1px solid #8a8a8a;
    border-radius: 4px;
    padding: 5px 9px;
    selection-background-color: {ACCENT};
    selection-color: #000000;
}}
QLineEdit:hover {{ background: #323232; }}
QLineEdit:focus {{ background: #1f1f1f; border-bottom: 2px solid {ACCENT}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#small {{ color: {MUTED}; font-size: 9pt; }}
QLabel#error {{ color: {ERROR}; font-size: 9pt; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 600; background: transparent; }}
QLabel#status {{ background: transparent; }}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#preview {{
    background: #1a1a1a;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QPushButton {{
    background: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover {{ background: #333333; }}
QPushButton:pressed {{ background: #282828; color: #cfcfcf; }}
QPushButton:disabled {{ background: #262626; color: #6b6b6b; border-color: #303030; }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #000000;
    font-weight: 600;
    padding: 9px 14px;
}}
QPushButton#primary:hover {{ background: #5bbbe8; border-color: #5bbbe8; }}
QPushButton#primary:pressed {{ background: #4aa6d1; border-color: #4aa6d1; color: #1a1a1a; }}
QPushButton#primary:disabled {{ background: #3a3a3a; border-color: #3a3a3a; color: #7a7a7a; }}
QToolTip {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+: también oscurece la barra de título
        hints.setColorScheme(Qt.ColorScheme.Dark)

    font = QFont("Segoe UI Variable Text")
    if not font.exactMatch():
        font = QFont("Segoe UI")
    font.setPointSizeF(10)
    app.setFont(font)

    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BACKGROUND,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: "#262626",
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: "#2d2d2d",
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#000000",
        QPalette.ColorRole.ToolTipBase: SURFACE,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: ACCENT,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#6b6b6b"))
    app.setPalette(palette)
    app.setStyleSheet(_STYLESHEET)


def render_icon(size: int) -> QImage:
    """Dibuja el icono: marco de captura con una flecha de guardado."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 64.0, size / 64.0)

    gradient = QLinearGradient(0, 0, 64, 64)
    gradient.setColorAt(0.0, QColor("#4cc2ff"))
    gradient.setColorAt(1.0, QColor("#0067c0"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)

    pen = QPen(QColor("#ffffff"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    corners = (
        ((14, 24), (14, 14), (24, 14)),
        ((40, 14), (50, 14), (50, 24)),
        ((14, 40), (14, 50), (24, 50)),
        ((40, 50), (50, 50), (50, 40)),
    )
    for corner in corners:
        painter.drawPolyline([QPointF(x, y) for x, y in corner])
    painter.drawLine(QPointF(32, 22), QPointF(32, 41))
    painter.drawPolyline([QPointF(25, 34), QPointF(32, 41), QPointF(39, 34)])
    painter.end()
    return image


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def make_app_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon(size)))
    return icon
