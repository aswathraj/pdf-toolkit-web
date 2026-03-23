@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
  python -m venv .venv
)

set "VENV_PY=.venv\Scripts\python.exe"

"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt -r requirements-windows-build.txt

powershell -ExecutionPolicy Bypass -File "scripts\prepare_tesseract.ps1" -InstallIfMissing
if errorlevel 1 exit /b 1

"%VENV_PY%" -m PyInstaller --noconfirm pdf_forge.spec

echo.
echo Build complete.
echo Windows executable: dist\PDFForge.exe
echo.

endlocal
