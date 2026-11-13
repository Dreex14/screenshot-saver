"""Detección de imágenes nuevas en el portapapeles de Windows.

Se basa en la señal ``QClipboard.dataChanged``. En Windows, Qt se registra como
oyente del portapapeles (AddClipboardFormatListener) y recibe WM_CLIPBOARDUPDATE
cada vez que cambia su contenido: no hay ningún bucle de sondeo.

La imagen se copia a un QImage propio en cuanto llega la notificación, antes de
que otra captura pueda reemplazarla. El portapapeles nunca se modifica.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage

from .winapi import clipboard_sequence_number

# Si el programa que publica la imagen aún tiene el portapapeles abierto, la
# lectura puede fallar; se reintenta unas pocas veces con esperas cortas.
_RETRY_DELAYS_MS = (25, 50, 100, 200, 400)

# Algunos programas publican la misma imagen en dos actualizaciones seguidas.
# Una imagen idéntica a la última guardada que llega dentro de este margen se
# trata como la misma captura. Fuera de él, dos capturas idénticas se guardan.
_SAME_EVENT_WINDOW_S = 0.6


class ClipboardWatcher(QObject):
    preview_changed = Signal(object)  # QImage, o None si no hay imagen
    image_captured = Signal(QImage)   # imagen nueva con el modo automático activo
    read_failed = Signal()            # había una imagen, pero no se pudo leer

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clipboard = QGuiApplication.clipboard()
        self._armed = False
        self._arm_sequence: int | None = None
        self._seen_sequence = clipboard_sequence_number()
        self._last_capture: QImage | None = None
        self._last_capture_time = 0.0
        self._clipboard.dataChanged.connect(self._on_data_changed)

    # --- Modo automático -------------------------------------------------

    @property
    def armed(self) -> bool:
        return self._armed

    def arm(self) -> None:
        """Empieza a aceptar imágenes. La que ya estuviera copiada se ignora."""
        self._arm_sequence = clipboard_sequence_number()
        self._armed = True

    def disarm(self) -> None:
        self._armed = False
        self._arm_sequence = None
        self._last_capture = None

    # --- Lectura -----------------------------------------------------------

    def current_image(self) -> QImage | None:
        """Imagen actual del portapapeles (para la vista previa y el guardado manual)."""
        mime = self._clipboard.mimeData()
        if mime is None or not mime.hasImage():
            return None
        image = self._clipboard.image()
        return None if image.isNull() else image

    def _on_data_changed(self) -> None:
        sequence = clipboard_sequence_number()
        if sequence == self._seen_sequence:
            return  # notificación repetida de una actualización ya tratada
        self._seen_sequence = sequence
        self._read(sequence, 0)

    def _read(self, sequence: int, attempt: int) -> None:
        if attempt and sequence != clipboard_sequence_number():
            return  # ya llegó otra actualización; esa se encarga

        mime = self._clipboard.mimeData()
        formats = mime.formats() if mime is not None else []
        if formats and not mime.hasImage():
            self.preview_changed.emit(None)  # texto, archivos u otro formato
            return

        image = self._clipboard.image() if formats else QImage()
        if image.isNull():
            # Sin formatos (portapapeles ocupado o vacío) o imagen ilegible.
            if attempt < len(_RETRY_DELAYS_MS):
                QTimer.singleShot(
                    _RETRY_DELAYS_MS[attempt], lambda: self._read(sequence, attempt + 1)
                )
                return
            self.preview_changed.emit(None)
            if formats and self._armed:
                self.read_failed.emit()
            return

        self.preview_changed.emit(image)

        if not self._armed or sequence == self._arm_sequence:
            return
        if self._is_same_capture(image):
            return
        self._last_capture = image
        self._last_capture_time = time.monotonic()
        QTimer.singleShot(int(_SAME_EVENT_WINDOW_S * 1000) + 100, self._expire_last_capture)
        self.image_captured.emit(image)

    def _is_same_capture(self, image: QImage) -> bool:
        last = self._last_capture
        if last is None or time.monotonic() - self._last_capture_time > _SAME_EVENT_WINDOW_S:
            return False
        rgb = QImage.Format.Format_RGB32
        return last.size() == image.size() and last.convertToFormat(rgb) == image.convertToFormat(rgb)

    def _expire_last_capture(self) -> None:
        # Libera la copia de referencia en cuanto deja de ser útil.
        if time.monotonic() - self._last_capture_time > _SAME_EVENT_WINDOW_S:
            self._last_capture = None
