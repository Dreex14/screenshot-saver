# -*- mode: python ; coding: utf-8 -*-
# Especificación de PyInstaller para Screenshot Saver.
# Uso:  python -m PyInstaller --noconfirm --clean ScreenshotSaver.spec
# Resultado: dist\ScreenshotSaver.exe (un solo archivo, sin consola).

# Partes de Qt que la aplicación no usa; quitarlas reduce mucho el tamaño.
UNUSED_QT = (
    "opengl32sw.dll",      # renderizado OpenGL por software (~20 MB)
    "qt6pdf",
    "qt6network",
    "qt6svg",
    "qt6qml",
    "qt6quick",
    "qt6virtualkeyboard",
    "qt6opengl",
    "\\imageformats\\",    # PNG ya está integrado en QtGui
    "\\iconengines\\",
    "\\generic\\",
    "\\networkinformation\\",
    "\\tls\\",
)


def _keep(entry):
    name = entry[0].lower().replace("/", "\\")
    return not any(part in name for part in UNUSED_QT)


a = Analysis(
    ["main.py"],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtNetwork", "PySide6.QtSvg", "PySide6.QtQml"],
    noarchive=False,
)
a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d) and "translations" not in d[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ScreenshotSaver",
    console=False,
    icon="assets/icon.ico",
    upx=False,
    debug=False,
    strip=False,
)
