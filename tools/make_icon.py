"""Genera assets/icon.ico (icono del .exe) a partir del dibujo de la aplicación.

Uso:  python tools/make_icon.py assets/icon.ico
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from screenshot_saver.ui.theme import ICON_SIZES, render_icon  # noqa: E402


def _png_bytes(size: int) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    render_icon(size).save(buffer, "PNG")
    return bytes(data.data())


def write_ico(path: Path) -> None:
    # Formato ICO con imágenes PNG embebidas (admitido desde Windows Vista).
    images = [(size, _png_bytes(size)) for size in ICON_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(payload))
        payload += png
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + payload)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv[:1])
    write_ico(Path(sys.argv[1] if len(sys.argv) > 1 else "assets/icon.ico"))
