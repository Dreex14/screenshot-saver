"""Widgets pequeños: interruptor, vista previa, etiqueta de ruta e indicador de estado."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QSizePolicy, QWidget

from . import theme


class ToggleSwitch(QAbstractButton):
    """Interruptor de encendido/apagado al estilo de Windows 11."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(self.sizeHint())

    def sizeHint(self) -> QSize:
        return QSize(44, 22)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = track.height() / 2
        enabled = self.isEnabled()

        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.ACCENT if enabled else "#4a4a4a"))
            knob_color = QColor("#000000" if enabled else "#7a7a7a")
        else:
            painter.setPen(QPen(QColor("#9a9a9a" if enabled else "#4a4a4a"), 1))
            painter.setBrush(QColor("#272727"))
            knob_color = QColor("#d0d0d0" if enabled else "#5a5a5a")
        painter.drawRoundedRect(track, radius, radius)

        knob = 14 if (self.underMouse() and enabled) else 12
        center_x = track.right() - radius if self.isChecked() else track.left() + radius
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(QRectF(center_x - knob / 2, track.center().y() - knob / 2, knob, knob))

        if self.hasFocus() and self.focusPolicy() != Qt.FocusPolicy.NoFocus:
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radius + 1, radius + 1)


class StatusDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(theme.IDLE)
        self.setFixedSize(10, 10)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(1, 1, 8, 8))


class ElidedLabel(QLabel):
    """Etiqueta que acorta el texto por el centro si no cabe (útil para rutas)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        # Pequeño margen: el ancho medido y el dibujado pueden diferir al escalar.
        width = max(0, self.contentsRect().width() - 6)
        self.setText(self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, width))


class ImagePreview(QFrame):
    """Miniatura de la imagen del portapapeles (solo visual; no altera la original)."""

    _MAX_THUMB = 1024  # se guarda una copia reducida, no la imagen completa

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview")
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._thumb: QImage | None = None

    def set_image(self, image: QImage | None) -> None:
        if image is None:
            self._thumb = None
        elif image.width() > self._MAX_THUMB or image.height() > self._MAX_THUMB:
            self._thumb = image.scaled(
                self._MAX_THUMB,
                self._MAX_THUMB,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            self._thumb = image
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        area = QRectF(self.contentsRect()).adjusted(10, 10, -10, -10)
        if self._thumb is None:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "No hay ninguna imagen\nen el portapapeles")
            return
        size = QSizeF(self._thumb.size())
        scale = min(area.width() / size.width(), area.height() / size.height(), 1.0)
        target = QSizeF(size.width() * scale, size.height() * scale)
        rect = QRectF(
            area.center().x() - target.width() / 2,
            area.center().y() - target.height() / 2,
            target.width(),
            target.height(),
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(rect, self._thumb)
