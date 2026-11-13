"""Ventana principal de Screenshot Saver."""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

from PySide6.QtCore import QEvent, QRegularExpression, Qt
from PySide6.QtGui import QImage, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import settings
from ..clipboard_watcher import ClipboardWatcher
from ..numbering import INVALID_NAME_CHARS, clean_prefix, file_name, next_number
from ..saver import ImageSaver
from ..winapi import use_dark_title_bar
from . import theme
from .widgets import ElidedLabel, ImagePreview, StatusDot, ToggleSwitch


def _section_title(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionTitle")
    return label


class MainWindow(QWidget):
    def __init__(self, watcher: ClipboardWatcher, saver: ImageSaver) -> None:
        super().__init__()
        self._watcher = watcher
        self._saver = saver
        self._folder = settings.load_last_folder()
        self._prefix = clean_prefix(settings.load_prefix())
        self._in_flight = 0          # capturas aceptadas que aún se están guardando
        self._error: str | None = None
        self._saved_count = 0
        self._last_saved: Path | None = None
        self._has_image = False
        self._title_bar_styled = False

        self.setWindowTitle("Screenshot Saver")
        self.resize(440, 680)
        self.setMinimumSize(380, 600)
        self._build_ui()

        watcher.preview_changed.connect(self._show_preview)
        watcher.image_captured.connect(self._on_image_captured)
        watcher.read_failed.connect(self._on_read_failed)
        saver.job_saved.connect(self._on_job_saved)
        saver.job_failed.connect(self._on_job_failed)

        self._show_preview(watcher.current_image())

    # --- Construcción ------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(8)

        # Carpeta de destino
        root.addWidget(_section_title("Carpeta de destino"))
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self._folder_label = ElidedLabel()
        self._folder_label.setObjectName("pathField")
        self._folder_label.setContentsMargins(10, 6, 10, 6)
        self._change_button = QPushButton("Cambiar…")
        self._change_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._change_button.clicked.connect(self._choose_folder)
        folder_row.addWidget(self._folder_label, 1)
        folder_row.addWidget(self._change_button)
        root.addLayout(folder_row)
        root.addSpacing(8)

        # Nombre opcional delante del número
        root.addWidget(_section_title("Nombre de archivo (opcional)"))
        self._prefix_edit = QLineEdit(self._prefix)
        self._prefix_edit.setPlaceholderText("Ej.: Proyecto Final  ·  vacío = 1.png, 2.png…")
        self._prefix_edit.setMaxLength(100)
        self._prefix_edit.setClearButtonEnabled(True)
        invalid = re.escape(INVALID_NAME_CHARS)
        self._prefix_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(f"[^{invalid}]*"), self._prefix_edit)
        )
        self._prefix_edit.setToolTip(
            "Se añade delante del número: «Proyecto Final 1.png».\n"
            "Cada nombre lleva su propia numeración.\n"
            f"No se admiten estos caracteres: {INVALID_NAME_CHARS}"
        )
        self._prefix_edit.textChanged.connect(self._on_prefix_changed)
        self._prefix_edit.editingFinished.connect(lambda: settings.save_prefix(self._prefix))
        root.addWidget(self._prefix_edit)
        root.addSpacing(8)

        # Vista previa
        root.addWidget(_section_title("Portapapeles"))
        self._preview = ImagePreview()
        root.addWidget(self._preview, 1)
        self._preview_info = QLabel()
        self._preview_info.setObjectName("small")
        root.addWidget(self._preview_info)
        root.addSpacing(8)

        # Modo automático
        card = QFrame()
        card.setObjectName("card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        title = QLabel("Modo automático")
        title.setObjectName("cardTitle")
        status_row = QHBoxLayout()
        status_row.setSpacing(7)
        self._status_dot = StatusDot()
        self._status_label = QLabel()
        self._status_label.setObjectName("status")
        status_row.addWidget(self._status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self._status_label, 1)
        texts.addWidget(title)
        texts.addLayout(status_row)
        self._auto_switch = ToggleSwitch()
        self._auto_switch.setToolTip("Guardar automáticamente cada imagen nueva del portapapeles")
        self._auto_switch.toggled.connect(self._on_auto_toggled)
        card_layout.addLayout(texts, 1)
        card_layout.addWidget(self._auto_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(card)
        root.addSpacing(6)

        # Siguiente archivo y guardado manual
        self._next_label = QLabel()
        self._next_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self._next_label)
        self._save_button = QPushButton("Guardar captura")
        self._save_button.setObjectName("primary")
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.clicked.connect(self._save_manually)
        root.addWidget(self._save_button)

        # Avisos y actividad
        self._error_label = QLabel()
        self._error_label.setObjectName("error")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)
        self._activity_label = QLabel()
        self._activity_label.setObjectName("small")
        root.addWidget(self._activity_label)

    # --- Estado ------------------------------------------------------------

    def _refresh(self) -> None:
        folder = self._folder
        folder_exists = folder is not None and os.path.isdir(folder)
        notice = self._error

        self._folder_label.set_full_text(folder or "Selecciona una carpeta para empezar")

        next_name = "—"
        if folder_exists:
            try:
                next_name = html.escape(file_name(next_number(folder, self._prefix), self._prefix))
            except OSError:
                notice = notice or f"No se puede leer la carpeta: {folder}"
        elif folder is not None:
            notice = notice or "La carpeta seleccionada ya no existe. Elige otra."
        self._next_label.setText(f"Siguiente archivo: <b>{next_name}</b>")

        self._auto_switch.setEnabled(folder is not None)
        self._save_button.setEnabled(folder is not None and self._has_image)

        if self._in_flight:
            text, color = "Guardando captura...", theme.ACCENT
        elif self._error:
            text, color = "Error al guardar", theme.ERROR
        elif self._watcher.armed:
            text, color = "Esperando capturas...", theme.SUCCESS
        else:
            text, color = "Modo automático desactivado", theme.IDLE
        self._status_label.setText(text)
        self._status_dot.set_color(color)

        self._error_label.setText(notice or "")
        self._error_label.setVisible(bool(notice))

        if self._last_saved is None:
            self._activity_label.setText("Ninguna captura guardada en esta sesión")
            self._activity_label.setToolTip("")
        else:
            plural = "captura guardada" if self._saved_count == 1 else "capturas guardadas"
            self._activity_label.setText(
                f"Último: {self._last_saved.name}  ·  {self._saved_count} {plural} en esta sesión"
            )
            self._activity_label.setToolTip(str(self._last_saved))

    def _show_preview(self, image: QImage | None) -> None:
        self._has_image = image is not None
        self._preview.set_image(image)
        if image is None:
            self._preview_info.setText("Sin imagen")
        else:
            self._preview_info.setText(f"{image.width()} × {image.height()} px")
        self._refresh()

    # --- Acciones ----------------------------------------------------------

    def _choose_folder(self) -> None:
        start = self._folder or str(Path.home() / "Pictures")
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino", start)
        if not folder:
            return
        self._folder = os.path.normpath(folder)
        settings.save_last_folder(self._folder)
        self._error = None
        self._refresh()

    def _on_prefix_changed(self, text: str) -> None:
        self._prefix = clean_prefix(text)
        self._refresh()

    def _on_auto_toggled(self, checked: bool) -> None:
        if checked:
            self._watcher.arm()
        else:
            self._watcher.disarm()
        self._error = None
        self._refresh()

    def _submit(self, image: QImage) -> None:
        if self._folder is None:
            return
        # Carpeta y nombre quedan fijados ahora: cambiarlos después no afecta a esta captura.
        self._saver.submit(image, self._folder, self._prefix)
        self._in_flight += 1
        self._refresh()

    def _on_image_captured(self, image: QImage) -> None:
        self._submit(image)

    def _save_manually(self) -> None:
        image = self._watcher.current_image()
        if image is None:
            self._show_preview(None)
            self._error = "No hay ninguna imagen en el portapapeles."
            self._refresh()
            return
        self._submit(image)

    def _on_read_failed(self) -> None:
        self._error = "Llegó una imagen al portapapeles, pero no se pudo leer. No se ha guardado."
        self._refresh()

    def _on_job_saved(self, job_id: int, path: str) -> None:
        self._in_flight -= 1
        self._saved_count += 1
        self._last_saved = Path(path)
        self._error = None
        self._refresh()

    def _on_job_failed(self, job_id: int, message: str) -> None:
        self._in_flight -= 1
        self._error = f"No se guardó la captura. {message}"
        self._refresh()

    # --- Eventos de ventana --------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._title_bar_styled:
            self._title_bar_styled = True
            use_dark_title_bar(int(self.winId()))

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self._refresh()  # la carpeta puede haber cambiado desde fuera

    def closeEvent(self, event) -> None:
        # Deja de aceptar capturas y termina de guardar las ya aceptadas.
        self._watcher.disarm()
        settings.save_prefix(self._prefix)
        if self._in_flight:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._saver.shutdown()
        event.accept()
