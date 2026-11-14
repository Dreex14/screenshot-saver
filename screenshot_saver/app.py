"""Punto de entrada de la aplicación."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .clipboard_watcher import ClipboardWatcher
from .saver import ImageSaver
from .ui.main_window import MainWindow
from .ui.theme import apply_theme, make_app_icon
from .winapi import set_app_user_model_id

APP_NAME = "Screenshot Saver"


def main() -> int:
    set_app_user_model_id("ScreenshotSaver.App")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(make_app_icon())
    apply_theme(app)

    # Una sola instancia: dos copias abiertas guardarían cada captura dos veces.
    lock_path = os.path.join(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation),
        "ScreenshotSaver.lock",
    )
    lock = QLockFile(lock_path)
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "Screenshot Saver ya está abierto.")
        return 0

    saver = ImageSaver()
    watcher = ClipboardWatcher()
    window = MainWindow(watcher, saver)
    window.show()
    exit_code = app.exec()

    saver.shutdown()  # por si la aplicación termina sin pasar por closeEvent
    lock.unlock()
    return exit_code
