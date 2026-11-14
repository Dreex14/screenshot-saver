# Genera dist\ScreenshotSaver.exe
# Uso (PowerShell, en la carpeta del proyecto):  .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }

python tools\make_icon.py assets\icon.ico
if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el icono." }

python -m PyInstaller --noconfirm --clean ScreenshotSaver.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ha fallado." }

Write-Host ""
Write-Host "Listo: $PSScriptRoot\dist\ScreenshotSaver.exe"
