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
if errorlevel 1 exit /b 1

set "ISCC_PATH="

if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC_PATH (
  for /f "delims=" %%I in ('where iscc 2^>nul') do set "ISCC_PATH=%%I"
)

if not defined ISCC_PATH (
  powershell -ExecutionPolicy Bypass -File "scripts\ensure_inno_setup.ps1"
  if errorlevel 1 exit /b 1
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_PATH (
  echo Inno Setup compiler not found.
  exit /b 1
)

"%ISCC_PATH%" "pdf_forge_installer.iss"
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Portable EXE: dist\PDFForge.exe
echo Installer EXE: installer_output\PDFForgeSetup.exe
echo.

endlocal
