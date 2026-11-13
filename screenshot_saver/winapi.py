"""Llamadas mínimas a la API de Windows mediante ctypes (sin dependencias extra)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32")
_user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
_user32.GetClipboardSequenceNumber.argtypes = []


def clipboard_sequence_number() -> int:
    """Número de serie que Windows incrementa con cada cambio del portapapeles.

    Permite distinguir dos actualizaciones distintas aunque su contenido sea
    idéntico, y descartar notificaciones repetidas de una misma actualización.
    """
    return int(_user32.GetClipboardSequenceNumber())


def set_app_user_model_id(app_id: str) -> None:
    """Hace que la barra de tareas muestre el icono propio al ejecutar desde código."""
    try:
        ctypes.WinDLL("shell32").SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
    except (OSError, AttributeError):
        pass


_DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def use_dark_title_bar(hwnd: int) -> None:
    """Barra de título oscura en Windows 11, a juego con el tema de la ventana."""
    try:
        value = ctypes.c_int(1)
        ctypes.WinDLL("dwmapi").DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(_DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except (OSError, AttributeError):
        pass
