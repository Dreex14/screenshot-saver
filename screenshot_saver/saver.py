"""Guardado de imágenes en PNG, en un hilo propio y en orden de llegada."""

from __future__ import annotations

import errno
import itertools
import queue
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, Signal
from PySide6.QtGui import QImage

from .numbering import file_name, next_number

# Límite de seguridad si otro programa crea archivos "N.png" sin parar.
_MAX_NAME_ATTEMPTS = 1000


class SaveError(Exception):
    """Error con un mensaje ya preparado para mostrarlo al usuario."""


def encode_png(image: QImage) -> bytes:
    """Codifica la imagen como PNG en memoria, con su resolución original."""
    image = _drop_empty_alpha(image)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    ok = image.save(buffer, "PNG")
    buffer.close()
    if not ok or data.isEmpty():
        raise SaveError("No se pudo convertir la imagen a PNG.")
    return bytes(data.data())


def _drop_empty_alpha(image: QImage) -> QImage:
    """Algunos programas publican mapas de bits de 32 bits con el canal alfa a 0.

    Guardados tal cual serían PNG totalmente transparentes; en ese caso el alfa
    no contiene información y la imagen se trata como opaca.
    """
    if not image.hasAlphaChannel():
        return image
    argb = image.convertToFormat(QImage.Format.Format_ARGB32)
    alpha = bytes(memoryview(argb.constBits())[3::4])  # byte A de cada píxel BGRA
    if alpha and alpha.count(0) == len(alpha):
        return image.convertToFormat(QImage.Format.Format_RGB32)
    return image


def write_numbered_file(data: bytes, folder: str | Path, prefix: str = "") -> Path:
    """Escribe ``data`` como el siguiente "[prefijo ]N.png" libre de la carpeta.

    El archivo se crea en modo exclusivo ("x"): si entre el cálculo del número
    y la escritura aparece un archivo con ese nombre, se prueba el siguiente.
    Nunca se sobrescribe un archivo existente.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(errno.ENOENT, "La carpeta no existe", str(folder))

    number = next_number(folder, prefix)
    for _ in range(_MAX_NAME_ATTEMPTS):
        path = folder / file_name(number, prefix)
        try:
            handle = open(path, "xb")
        except FileExistsError:
            number += 1
            continue
        try:
            with handle:
                handle.write(data)
        except BaseException:
            # Solo se borra el archivo que acabamos de crear nosotros, incompleto.
            try:
                path.unlink()
            except OSError:
                pass
            raise
        return path
    raise SaveError("No se encontró un nombre de archivo libre.")


def describe_error(exc: BaseException, folder: str) -> str:
    if isinstance(exc, SaveError):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return f"La carpeta no existe: {folder}"
    if isinstance(exc, PermissionError):
        return f"No hay permiso para escribir en: {folder}"
    if isinstance(exc, OSError):
        if exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) in (39, 112):
            return "No queda espacio en el disco."
        return f"No se pudo escribir el archivo ({exc.strerror or exc})."
    return f"Error inesperado: {exc}"


@dataclass(frozen=True)
class _Job:
    job_id: int
    image: QImage
    folder: str
    prefix: str


class ImageSaver(QObject):
    """Cola de guardado procesada por un único hilo de trabajo.

    Cada trabajo lleva su propia carpeta y nombre, fijados en el momento de
    aceptarlo, así que cambiarlos después no afecta a lo que ya está en cola.
    Al ser un solo hilo, los archivos reciben los números en orden de llegada.
    """

    job_saved = Signal(int, str)   # id, ruta del archivo creado
    job_failed = Signal(int, str)  # id, mensaje de error

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._queue: queue.Queue[_Job | None] = queue.Queue()
        self._ids = itertools.count(1)
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="ImageSaver", daemon=True)
        self._thread.start()

    def submit(self, image: QImage, folder: str, prefix: str = "") -> int:
        if self._closed:
            raise RuntimeError("El guardado ya se ha detenido.")
        job = _Job(next(self._ids), QImage(image), folder, prefix)
        self._queue.put(job)
        return job.job_id

    def shutdown(self, timeout: float = 30.0) -> bool:
        """Termina los trabajos pendientes y detiene el hilo. Devuelve True si acabó."""
        if not self._closed:
            self._closed = True
            self._queue.put(None)
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            try:
                path = write_numbered_file(encode_png(job.image), job.folder, job.prefix)
            except Exception as exc:  # noqa: BLE001 - cualquier fallo se notifica
                self.job_failed.emit(job.job_id, describe_error(exc, job.folder))
            else:
                self.job_saved.emit(job.job_id, str(path))
