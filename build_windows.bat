@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
  py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-windows-build.txt

powershell -ExecutionPolicy Bypass -File "scripts\prepare_tesseract.ps1" -InstallIfMissing
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm pdf_forge.spec

echo.
echo Build complete.
echo Windows executable: dist\PDFForge.exe
echo.

endlocal
