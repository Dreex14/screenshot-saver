"""Configuración local en %APPDATA%\\ScreenshotSaver\\ScreenshotSaver.ini."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

_KEY_FOLDER = "last_folder"
_KEY_PREFIX = "name_prefix"


def _settings() -> QSettings:
    return QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, "ScreenshotSaver", "ScreenshotSaver"
    )


def load_last_folder() -> str | None:
    """Última carpeta usada, solo si sigue existiendo."""
    folder = _settings().value(_KEY_FOLDER, "", type=str)
    return folder if folder and os.path.isdir(folder) else None


def save_last_folder(folder: str) -> None:
    settings = _settings()
    settings.setValue(_KEY_FOLDER, folder)
    settings.sync()


def load_prefix() -> str:
    return _settings().value(_KEY_PREFIX, "", type=str)


def save_prefix(prefix: str) -> None:
    settings = _settings()
    settings.setValue(_KEY_PREFIX, prefix)
    settings.sync()
