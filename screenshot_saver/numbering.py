"""Numeración consecutiva de archivos, con un nombre opcional delante.

Sin nombre:              1.png, 2.png, 3.png...
Con "Proyecto Final":  Proyecto Final 1.png, Proyecto Final 2.png...

Cada nombre lleva su propia numeración dentro de la carpeta. El siguiente número
se calcula siempre leyendo el contenido real de la carpeta; no se guarda ningún
contador en archivos externos.
"""

from __future__ import annotations

import os
import re

# Caracteres que Windows no admite en nombres de archivo.
INVALID_NAME_CHARS = '<>:"/\\|?*'


def clean_prefix(prefix: str | None) -> str:
    """Nombre listo para usar: sin espacios sobrantes ni caracteres no válidos."""
    if not prefix:
        return ""
    cleaned = "".join(ch for ch in prefix if ch not in INVALID_NAME_CHARS and ord(ch) >= 32)
    return " ".join(cleaned.split())


def _pattern(prefix: str) -> re.Pattern[str]:
    # Solo dígitos ASCII (no "１２") y .png sin distinguir mayúsculas, igual que
    # Windows tampoco distingue mayúsculas en los nombres.
    lead = re.escape(prefix) + " " if prefix else ""
    return re.compile(lead + r"([0-9]+)\.png", re.IGNORECASE)


def numeric_png_value(name: str, prefix: str = "") -> int | None:
    """Devuelve N si ``name`` es exactamente "[prefijo ]N.png" con N entero positivo."""
    match = _pattern(clean_prefix(prefix)).fullmatch(name)
    if match is None:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def highest_number(folder: str | os.PathLike[str], prefix: str = "") -> int:
    """Mayor N de los archivos "[prefijo ]N.png" de la carpeta, o 0 si no hay ninguno."""
    pattern = _pattern(clean_prefix(prefix))
    highest = 0
    with os.scandir(folder) as entries:
        for entry in entries:
            match = pattern.fullmatch(entry.name)
            if match is not None:
                highest = max(highest, int(match.group(1)))
    return highest


def next_number(folder: str | os.PathLike[str], prefix: str = "") -> int:
    """Siguiente número disponible para ese nombre: el más alto existente más uno."""
    return highest_number(folder, prefix) + 1


def file_name(number: int, prefix: str = "") -> str:
    prefix = clean_prefix(prefix)
    return f"{prefix} {number}.png" if prefix else f"{number}.png"
