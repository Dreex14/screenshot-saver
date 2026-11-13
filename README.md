# Screenshot Saver

Pequeña utilidad para Windows 11 que guarda las imágenes del portapapeles en una
carpeta, con nombres numéricos consecutivos: `1.png`, `2.png`, `3.png`...

Haces la captura con `Impr Pant` o `Win + Shift + S` como siempre, y la imagen
aparece guardada en la carpeta elegida. Sin Paint, sin `Ctrl + S`, sin diálogos.

## Uso

1. Pulsa **Cambiar…** y elige la carpeta de destino.
2. **Nombre de archivo (opcional)**: si escribes, por ejemplo, `Proyecto Final`,
   las capturas se guardan como `Proyecto Final 1.png`, `Proyecto Final 2.png`...
   Si lo dejas vacío se guardan como `1.png`, `2.png`... Se recuerda entre sesiones.
3. **Modo automático** (interruptor): mientras está activo, cada imagen nueva que
   llega al portapapeles se guarda al instante. Puedes seguir jugando o trabajando
   sin volver a la ventana.
4. **Guardar captura**: guarda manualmente la imagen que hay ahora en el
   portapapeles (aunque hayas hecho la captura antes de abrir el programa).

La ventana muestra una vista previa del portapapeles, el nombre del siguiente
archivo, el estado del modo automático y el último archivo guardado.

### Numeración

- Se buscan en la carpeta los archivos `N.png` cuyo nombre es solo un número
  entero positivo; el siguiente es el mayor + 1. Carpeta sin ellos → `1.png`.
  Ejemplo: `1.png 2.png 5.png 8.png` → `9.png`.
- Con nombre, se buscan los archivos `Nombre N.png` (sin distinguir mayúsculas).
  Cada nombre lleva su propia numeración aunque comparta carpeta: si hay `1.png`,
  `2.png` y escribes `Antonio`, la siguiente será `Antonio 1.png`.
- Se calcula siempre leyendo la carpeta real (no hay contadores guardados), así
  que cada carpeta tiene su propia numeración.
- Cambiar la carpeta o el nombre no afecta a las capturas que ya se están
  guardando: cada una conserva los que había al llegar.
- El nombre no admite los caracteres que Windows prohíbe: `< > : " / \ | ? *`.
- Nunca se sobrescribe nada: el archivo se crea en modo exclusivo y, si mientras
  tanto aparece otro con ese nombre, se usa el siguiente número.

### A tener en cuenta

- Windows no permite saber de forma fiable de dónde viene una imagen, así que
  **cualquier imagen nueva** del portapapeles se guarda en modo automático (por
  ejemplo, “Copiar imagen” en el navegador, o copiar celdas en Excel, que también
  publica una imagen). El texto, los archivos y otros formatos se ignoran.
- La imagen que ya estaba copiada al activar el modo automático **no** se guarda.
- Dos capturas idénticas hechas por separado se guardan como dos archivos. Solo
  si una misma imagen llega dos veces en menos de 0,6 s se considera la misma
  captura (algunos programas la publican en dos pasos).
- Solo se pueden guardar las imágenes que el programa llega a ver: si otra
  captura reemplaza a la anterior antes de poder leerla, la anterior se pierde.
  En las pruebas, tres capturas con 150 ms de separación se guardaron todas.
- Si falla el guardado (carpeta borrada, sin permisos, disco lleno) se muestra el
  error en la ventana; nunca se indica como guardada una captura que no lo está.
- Al cerrar la ventana el programa termina por completo (después de terminar de
  escribir las capturas ya aceptadas). Solo puede haber una instancia abierta.

### Privacidad

Funciona sin Internet: sin conexiones, sin telemetría, sin cuentas. No necesita
permisos de administrador, no se inicia con Windows y nunca modifica ni vacía el
portapapeles. Solo recuerda la última carpeta y el nombre, en
`%APPDATA%\ScreenshotSaver\ScreenshotSaver.ini`.

## Ejecutar desde el código

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
```

```bash
pythonw main.py
```

(`pythonw` evita la ventana de consola; `python main.py` también funciona.)

## Generar el ejecutable

```powershell
.\build.ps1
```

Instala PySide6 y PyInstaller, genera el icono y crea **`dist\ScreenshotSaver.exe`**
(un único archivo de ~25 MB, sin consola, sin instalar nada más). Puedes copiarlo
donde quieras.

Equivalente manual:

```bash
pip install -r requirements.txt pyinstaller
```

```bash
python tools\make_icon.py assets\icon.ico
```

```bash
python -m PyInstaller --noconfirm --clean ScreenshotSaver.spec
```

## Estructura

```text
main.py                         punto de entrada
screenshot_saver/
    app.py                      arranque, tema, instancia única
    clipboard_watcher.py        detección de imágenes nuevas (por eventos)
    numbering.py                cálculo del siguiente N.png
    saver.py                    codificación PNG y escritura en un hilo propio
    settings.py                 última carpeta (AppData)
    winapi.py                   llamadas mínimas a Windows (ctypes)
    ui/                         ventana, widgets y tema oscuro
tests/                          pruebas
ScreenshotSaver.spec, build.ps1 generación del .exe
```

La detección usa la señal `QClipboard.dataChanged`: en Windows, Qt se registra
como oyente del portapapeles y recibe un aviso del sistema en cada cambio. No hay
ningún bucle consultando el portapapeles.

## Pruebas

Pruebas unitarias (numeración, guardado, cola, errores):

```bash
python -m unittest discover -s tests -t . -v
```

Prueba de integración con el portapapeles real de Windows (otro proceso publica
imágenes y texto). **Sustituye el contenido de tu portapapeles**:

```bash
python -m tests.integration_clipboard
```

### Comprobación manual con capturas reales

| # | Caso | Qué hacer | Resultado esperado |
|---|------|-----------|--------------------|
| 1 | Carpeta vacía | Elige una carpeta vacía, activa el modo, `Win + Shift + S` | `1.png` |
| 2 | Carpeta con capturas | Carpeta con `1.png`, `2.png`, `5.png` | Siguiente: `6.png` |
| 3 | Cambio de carpeta | Cambia a otra carpeta vacía y captura | `1.png` en la nueva |
| 4 | Modo desactivado | Modo apagado, `Impr Pant` | No se crea nada |
| 5 | Modo activado | Modo encendido, `Impr Pant` | Archivo nuevo al instante |
| 6 | Varias seguidas | Varias capturas rápidas | Nombres sucesivos |
| 7 | Capturas idénticas | `Impr Pant` dos veces sin cambiar la pantalla | Dos archivos |
| 8 | Texto | Copia un texto con el modo activo | No se crea nada |
| 9 | Imagen previa | Copia una imagen y después activa el modo | No se guarda |
| 10 | Carpeta inexistente | Elige una carpeta, bórrala y captura | Aviso de error en rojo |
| 11 | Reinicio | Cierra y vuelve a abrir | Recupera la carpeta |
| 12 | Cierre | Cierra la ventana | No queda `ScreenshotSaver.exe` en el Administrador de tareas |

En Windows 11, `Impr Pant` abre por defecto la herramienta Recortes; la captura
llega igualmente al portapapeles cuando terminas la selección.

## Licencia

El código de este proyecto se distribuye bajo la licencia [MIT](LICENSE).
Copyright (c) 2026 Dreex.

Las dependencias conservan sus propias licencias:

| Dependencia | Uso | Licencia |
|-------------|-----|----------|
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) | Interfaz y acceso al portapapeles | [LGPL v3](https://www.gnu.org/licenses/lgpl-3.0.html) |
| [Qt 6](https://www.qt.io/) (incluido en PySide6) | Biblioteca gráfica | [LGPL v3](https://doc.qt.io/qt-6/lgpl.html) |
| [PyInstaller](https://pyinstaller.org/) | Generación del `.exe` (solo al compilar) | [GPL v2 con excepción para el ejecutable](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) |
| [Python](https://www.python.org/) | Lenguaje e intérprete incluido en el `.exe` | [PSF License](https://docs.python.org/3/license.html) |

La excepción de PyInstaller permite distribuir el `.exe` generado con cualquier
licencia. Qt y PySide6 se usan como bibliotecas, sin modificar.

---

Hecho por **Dreex**.
