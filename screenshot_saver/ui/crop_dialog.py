"""Recortador opcional para el guardado manual.

Muestra la captura con un marco de recorte: se ajusta arrastrando las esquinas
o los bordes, se mueve arrastrando por dentro y se dibuja uno nuevo arrastrando
por fuera. El recorte se hace sobre los píxeles originales, sin reescalar.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..winapi import use_dark_title_bar

# Recorte como (izquierda, arriba, derecha, abajo) en píxeles de la imagen;
# derecha y abajo son exclusivos, así que el ancho es derecha - izquierda.
Edges = tuple[int, int, int, int]

# Bordes que mueve cada asa: (izquierdo, superior, derecho, inferior).
HANDLES: dict[str, tuple[bool, bool, bool, bool]] = {
    "tl": (True, True, False, False),
    "tr": (False, True, True, False),
    "bl": (True, False, False, True),
    "br": (False, False, True, True),
    "l": (True, False, False, False),
    "r": (False, False, True, False),
    "t": (False, True, False, False),
    "b": (False, False, False, True),
}

_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "l": Qt.CursorShape.SizeHorCursor,
    "r": Qt.CursorShape.SizeHorCursor,
    "t": Qt.CursorShape.SizeVerCursor,
    "b": Qt.CursorShape.SizeVerCursor,
    "move": Qt.CursorShape.SizeAllCursor,
}


# --- Geometría (funciones puras, fáciles de probar) ---------------------------


def resize_edges(start: Edges, moving: tuple[bool, bool, bool, bool], dx: int, dy: int,
                 width: int, height: int, min_size: int) -> Edges:
    """Desplaza los bordes indicados sin salir de la imagen ni bajar del mínimo."""
    left, top, right, bottom = start
    move_left, move_top, move_right, move_bottom = moving
    min_w = min(min_size, width)
    min_h = min(min_size, height)
    if move_left:
        left = min(max(left + dx, 0), right - min_w)
    if move_right:
        right = max(min(right + dx, width), left + min_w)
    if move_top:
        top = min(max(top + dy, 0), bottom - min_h)
    if move_bottom:
        bottom = max(min(bottom + dy, height), top + min_h)
    return left, top, right, bottom


def move_edges(start: Edges, dx: int, dy: int, width: int, height: int) -> Edges:
    """Mueve el recorte entero manteniéndolo dentro de la imagen."""
    left, top, right, bottom = start
    w, h = right - left, bottom - top
    left = min(max(left + dx, 0), width - w)
    top = min(max(top + dy, 0), height - h)
    return left, top, left + w, top + h


def span_edges(ax: int, ay: int, bx: int, by: int, width: int, height: int) -> Edges:
    """Recorte nuevo entre dos puntos, en cualquier dirección, dentro de la imagen."""
    ax, bx = (min(max(v, 0), width) for v in (ax, bx))
    ay, by = (min(max(v, 0), height) for v in (ay, by))
    return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)


# --- Lienzo ------------------------------------------------------------------


class CropCanvas(QWidget):
    selection_changed = Signal(QRect)
    accept_requested = Signal()

    _MARGIN = 16        # espacio alrededor de la imagen, para poder agarrar las esquinas
    _HIT = 12           # tolerancia en píxeles de pantalla para agarrar asas
    _MIN_DISPLAY = 16   # tamaño mínimo del recorte, en píxeles de pantalla
    _MAX_ZOOM = 8.0     # las imágenes pequeñas se amplían como mucho 8 veces

    def __init__(self, image: QImage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image = image
        self._w = image.width()
        self._h = image.height()
        self._sel: Edges = (0, 0, self._w, self._h)
        self._drag: tuple | None = None
        self._scale = 1.0
        self._target = QRectF()
        self._pixmap: QPixmap | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # Estado

    def selection(self) -> QRect:
        left, top, right, bottom = self._sel
        return QRect(left, top, right - left, bottom - top)

    def set_selection(self, edges: Edges) -> None:
        if edges != self._sel:
            self._sel = edges
            self.selection_changed.emit(self.selection())
            self.update()

    def reset(self) -> None:
        self.set_selection((0, 0, self._w, self._h))

    def sizeHint(self) -> QSize:
        return QSize(900, 600)

    # Conversión de coordenadas

    def _relayout(self) -> None:
        area = QRectF(self.rect()).adjusted(self._MARGIN, self._MARGIN, -self._MARGIN, -self._MARGIN)
        if area.width() <= 0 or area.height() <= 0:
            return
        self._scale = min(area.width() / self._w, area.height() / self._h, self._MAX_ZOOM)
        tw, th = self._w * self._scale, self._h * self._scale
        self._target = QRectF(area.center().x() - tw / 2, area.center().y() - th / 2, tw, th)
        # Se guarda una copia ya escalada: redibujar al arrastrar es instantáneo.
        dpr = self.devicePixelRatioF()
        mode = (Qt.TransformationMode.SmoothTransformation if self._scale < 1
                else Qt.TransformationMode.FastTransformation)  # al ampliar, píxeles nítidos
        scaled = self._image.scaled(max(1, round(tw * dpr)), max(1, round(th * dpr)),
                                    Qt.AspectRatioMode.IgnoreAspectRatio, mode)
        self._pixmap = QPixmap.fromImage(scaled)
        self._pixmap.setDevicePixelRatio(dpr)

    def _to_widget(self, x: float, y: float) -> QPointF:
        return QPointF(self._target.x() + x * self._scale, self._target.y() + y * self._scale)

    def _to_image(self, pos: QPointF) -> tuple[float, float]:
        return ((pos.x() - self._target.x()) / self._scale, (pos.y() - self._target.y()) / self._scale)

    def _selection_rect(self) -> QRectF:
        left, top, right, bottom = self._sel
        return QRectF(self._to_widget(left, top), self._to_widget(right, bottom))

    def _min_size(self) -> int:
        return max(1, math.ceil(self._MIN_DISPLAY / self._scale))

    def _hit(self, pos: QPointF) -> str | None:
        rect = self._selection_rect()
        tol = self._HIT
        corners = {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
        }
        for name, point in corners.items():
            if abs(pos.x() - point.x()) <= tol and abs(pos.y() - point.y()) <= tol:
                return name
        inside_x = rect.left() <= pos.x() <= rect.right()
        inside_y = rect.top() <= pos.y() <= rect.bottom()
        if inside_y and abs(pos.x() - rect.left()) <= tol:
            return "l"
        if inside_y and abs(pos.x() - rect.right()) <= tol:
            return "r"
        if inside_x and abs(pos.y() - rect.top()) <= tol:
            return "t"
        if inside_x and abs(pos.y() - rect.bottom()) <= tol:
            return "b"
        if rect.contains(pos):
            return "move"
        return None

    # Ratón

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        hit = self._hit(pos)
        point = self._to_image(pos)
        if hit in HANDLES:
            self._drag = ("resize", self._sel, point, HANDLES[hit])
        elif hit == "move":
            self._drag = ("move", self._sel, point, None)
        elif self._target.adjusted(-self._HIT, -self._HIT, self._HIT, self._HIT).contains(pos):
            self._drag = ("new", self._sel, point, None)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        if self._drag is None:
            hit = self._hit(pos)
            if hit is not None:
                self.setCursor(_CURSORS[hit])
            elif self._target.contains(pos):
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.unsetCursor()
            return

        mode, start, (sx, sy), moving = self._drag
        ix, iy = self._to_image(pos)
        dx, dy = round(ix - sx), round(iy - sy)
        if mode == "resize":
            self.set_selection(resize_edges(start, moving, dx, dy, self._w, self._h, self._min_size()))
        elif mode == "move":
            self.set_selection(move_edges(start, dx, dy, self._w, self._h))
        else:
            edges = span_edges(round(sx), round(sy), round(ix), round(iy), self._w, self._h)
            if edges[2] > edges[0] and edges[3] > edges[1]:
                self.set_selection(edges)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag is None:
            return
        mode, start, _point, _moving = self._drag
        self._drag = None
        left, top, right, bottom = self._sel
        if mode == "new" and min(right - left, bottom - top) < min(self._min_size(), self._w, self._h):
            self.set_selection(start)  # un clic suelto no deshace el recorte anterior
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._selection_rect().contains(event.position()):
            self.accept_requested.emit()

    # Dibujo

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141414"))
        if self._pixmap is None:
            return
        painter.drawPixmap(self._target.topLeft(), self._pixmap)

        sel = self._selection_rect()
        shade = QPainterPath()
        shade.addRect(self._target)
        shade.addRect(sel)  # regla par-impar: el recorte queda como hueco sin oscurecer
        painter.fillPath(shade, QColor(0, 0, 0, 155))

        if self._drag is not None:  # guías de tercios mientras se ajusta
            painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
            for i in (1, 2):
                x = sel.left() + sel.width() * i / 3
                y = sel.top() + sel.height() * i / 3
                painter.drawLine(QPointF(x, sel.top()), QPointF(x, sel.bottom()))
                painter.drawLine(QPointF(sel.left(), y), QPointF(sel.right(), y))

        painter.setPen(QPen(QColor(255, 255, 255, 230), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sel)

        # Esquinas en L, gruesas y fáciles de agarrar.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#ffffff"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        arm = min(20.0, sel.width() / 2, sel.height() / 2)
        o = 1.5  # las L quedan justo por fuera del borde
        l, t, r, b = sel.left() - o, sel.top() - o, sel.right() + o, sel.bottom() + o
        for (cx, cy, hx, vy) in ((l, t, arm, arm), (r, t, -arm, arm), (l, b, arm, -arm), (r, b, -arm, -arm)):
            painter.drawLine(QPointF(cx, cy), QPointF(cx + hx, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + vy))

        # Asas pequeñas en el centro de cada borde, si hay sitio.
        bar = 9.0
        if sel.width() > 70:
            for y in (t, b):
                painter.drawLine(QPointF(sel.center().x() - bar, y), QPointF(sel.center().x() + bar, y))
        if sel.height() > 70:
            for x in (l, r):
                painter.drawLine(QPointF(x, sel.center().y() - bar), QPointF(x, sel.center().y() + bar))

        self._draw_size_label(painter, sel)

    def _draw_size_label(self, painter: QPainter, sel: QRectF) -> None:
        rect = self.selection()
        text = f"{rect.width()} × {rect.height()}"
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(text) + 14
        h = metrics.height() + 6
        x = sel.left()
        y = sel.top() - h - 8
        if y < 2:  # sin sitio encima: dentro del recorte
            x, y = sel.left() + 8, sel.top() + 8
        x = min(max(x, 2), self.width() - w - 2)
        box = QRectF(x, y, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 185))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


# --- Diálogo -----------------------------------------------------------------


class CropDialog(QDialog):
    def __init__(self, image: QImage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image = image
        self._title_bar_styled = False
        self.setWindowTitle("Recortar captura")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._canvas = CropCanvas(image)
        self._canvas.selection_changed.connect(self._update_info)
        self._canvas.accept_requested.connect(self.accept)

        hint = QLabel(
            "Arrastra las esquinas o los bordes para ajustar el recorte. "
            "Arrastra dentro para moverlo o fuera para hacer uno nuevo."
        )
        hint.setObjectName("small")
        hint.setWordWrap(True)

        self._info = QLabel()
        self._info.setObjectName("muted")

        reset = QPushButton("Restablecer")
        reset.setToolTip("Volver a seleccionar la imagen completa")
        reset.clicked.connect(self._canvas.reset)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar recorte")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        for button in (reset, cancel, save):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self._info, 1)
        buttons.addWidget(reset)
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(hint)
        layout.addWidget(self._canvas, 1)
        layout.addLayout(buttons)

        screen = parent.screen() if parent is not None else QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        self.resize(int(available.width() * 0.72), int(available.height() * 0.8))
        self.setMinimumSize(600, 440)
        self._update_info(self._canvas.selection())
        self._canvas.setFocus()

    def cropped_image(self) -> QImage:
        """Copia de los píxeles originales dentro del recorte."""
        return self._image.copy(self._canvas.selection())

    def _update_info(self, rect: QRect) -> None:
        self._info.setText(
            f"Recorte: {rect.width()} × {rect.height()} px   ·   "
            f"Original: {self._image.width()} × {self._image.height()} px"
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._title_bar_styled:
            self._title_bar_styled = True
            use_dark_title_bar(int(self.winId()))
