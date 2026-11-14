"""Prueba de integración con el portapapeles REAL de Windows.

Otro proceso (PowerShell) publica imágenes y texto en el portapapeles, igual que
lo haría cualquier programa, y se comprueba qué archivos genera la aplicación.

ATENCIÓN: sustituye el contenido actual de tu portapapeles.

Uso:  python -m tests.integration_clipboard
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEventLoop, QProcess, QTimer
from PySide6.QtWidgets import QApplication

from screenshot_saver.clipboard_watcher import ClipboardWatcher
from screenshot_saver.saver import ImageSaver
from screenshot_saver.winapi import clipboard_sequence_number

_PS_PRELUDE = r"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
function Put-Image($r, $g, $b, $w = 320, $h = 200) {
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.Clear([System.Drawing.Color]::FromArgb($r, $g, $b))
    $gfx.Dispose()
    [System.Windows.Forms.Clipboard]::SetImage($bmp)
    $bmp.Dispose()
}
function Put-Screen {
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $gfx.Dispose()
    [System.Windows.Forms.Clipboard]::SetImage($bmp)
    $bmp.Dispose()
    Write-Output "$($bounds.Width)x$($bounds.Height)"
}
"""


def pump(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def powershell(script: str) -> str:
    """Ejecuta PowerShell sin bloquear el bucle de eventos de Qt."""
    process = QProcess()
    process.start("powershell.exe", ["-NoProfile", "-STA", "-Command", _PS_PRELUDE + script])
    while process.state() != QProcess.ProcessState.NotRunning:
        pump(20)
    return bytes(process.readAllStandardOutput().data()).decode(errors="replace").strip()


def main() -> int:
    app = QApplication(sys.argv)
    watcher = ClipboardWatcher()
    saver = ImageSaver()
    saved: list[Path] = []
    errors: list[str] = []
    saver.job_saved.connect(lambda _i, p: saved.append(Path(p)))
    saver.job_failed.connect(lambda _i, m: errors.append(m))

    folder_a = Path(tempfile.mkdtemp(prefix="ssaver_a_"))
    folder_b = Path(tempfile.mkdtemp(prefix="ssaver_b_"))
    current = {"folder": folder_a}
    watcher.image_captured.connect(lambda img: saver.submit(img, str(current["folder"])))

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"[{'OK' if ok else 'FALLO'}] {name} {detail}")

    def files(folder: Path) -> list[str]:
        return sorted((p.name for p in folder.glob("*.png")), key=lambda n: int(n[:-4]))

    def settle(ms: int = 1200) -> None:
        pump(ms)

    # 4. Modo automático desactivado: no se guarda nada.
    powershell("Put-Image 10 20 30")
    settle()
    check("4. Captura con modo automático desactivado", files(folder_a) == [], str(files(folder_a)))

    # 9. Imagen ya presente al activar el modo: no se guarda.
    watcher.arm()
    settle()
    check("9. Imagen previa al activar el modo", files(folder_a) == [], str(files(folder_a)))

    # 5. Modo automático activado: guardado inmediato.
    powershell("Put-Image 200 0 0")
    settle()
    check("5. Captura con modo automático activado", files(folder_a) == ["1.png"], str(files(folder_a)))

    # No se modifica el portapapeles al guardar.
    seq_before = clipboard_sequence_number()
    settle(500)
    check("   El portapapeles no se modifica", clipboard_sequence_number() == seq_before)

    # 8. Texto: ningún archivo.
    powershell("Set-Clipboard -Value 'hola'")
    settle()
    check("8. Portapapeles con texto", files(folder_a) == ["1.png"], str(files(folder_a)))

    # 7. Dos capturas idénticas en dos eventos distintos.
    powershell("Put-Image 0 120 0")
    settle()
    powershell("Put-Image 0 120 0")
    settle()
    check("7. Dos capturas idénticas", files(folder_a) == ["1.png", "2.png", "3.png"], str(files(folder_a)))

    # 6. Varias capturas consecutivas y rápidas (150 ms entre ellas).
    powershell("Put-Image 1 1 1; Start-Sleep -Milliseconds 150; Put-Image 2 2 2; "
               "Start-Sleep -Milliseconds 150; Put-Image 3 3 3")
    settle(2000)
    check("6. Capturas consecutivas", files(folder_a) == [f"{n}.png" for n in range(1, 7)], str(files(folder_a)))

    # 3. Cambio de carpeta: numeración independiente.
    current["folder"] = folder_b
    powershell("Put-Image 50 50 200")
    settle()
    check("3. Cambio de carpeta", files(folder_b) == ["1.png"] and len(files(folder_a)) == 6,
          f"A={files(folder_a)} B={files(folder_b)}")

    # Captura de pantalla completa (imagen grande, como Impr Pant).
    dims = powershell("Put-Screen")
    settle(2500)
    from PySide6.QtGui import QImage
    shot = QImage(str(folder_b / "2.png"))
    check("   Pantalla completa a resolución original",
          (folder_b / "2.png").exists() and f"{shot.width()}x{shot.height()}" == dims,
          f"esperado {dims}, guardado {shot.width()}x{shot.height()}")

    # Al desactivar, no se aceptan nuevas imágenes.
    watcher.disarm()
    powershell("Put-Image 9 9 9")
    settle()
    check("   Tras desactivar no se guarda", files(folder_b) == ["1.png", "2.png"], str(files(folder_b)))

    check("   Sin errores de guardado", not errors, str(errors))
    saver.shutdown()
    del app

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} comprobaciones correctas")
    print(f"Archivos de prueba en: {folder_a} y {folder_b}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
