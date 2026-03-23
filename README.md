# PDF Forge

Local Flask app for PDF and document processing, inspired by iLovePDF-style workflows.

## Features

- JPG, JPEG, PNG, WEBP to PDF
- PDF to JPG
- DOCX to PDF
- PDF to DOCX
- XLSX to PDF
- PDF to XLSX
- Merge PDF
- Split PDF by page or custom ranges
- Remove annotations and optional watermark text
- OCR scanned PDFs and images into searchable PDFs

## Notes

- The app removes the Flask upload cap with `MAX_CONTENT_LENGTH = None`.
- There is no artificial app-side file-size limit, but real capacity still depends on disk, RAM, and any web server/proxy you place in front of Flask.
- DOCX and XLSX to PDF here prioritize readable conversion of text and tables. They are not pixel-perfect layout clones of Microsoft Office exports.
- Watermark removal works best when you provide the watermark text in the form field.
- OCR requires the `tesseract` binary to be installed on the machine or bundled with the packaged app.

## Setup

```bash
cd "/Users/aswathraj/Documents/codex 1/pdf_toolkit_web"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
brew install tesseract
python3 app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000).

If port 5000 is already in use:

```bash
HOST=127.0.0.1 PORT=5050 FLASK_DEBUG=0 python3 app.py
```

## macOS DMG Build

This Mac can build a local `.app` bundle and `.dmg` for the current project.

```bash
cd "/Users/aswathraj/Documents/codex 1/pdf_toolkit_web"
chmod +x build_mac_dmg.sh
./build_mac_dmg.sh
```

That produces:

```text
dist/PDF Forge.app
release/PDFForge-macOS.dmg
```

Notes for the macOS build:

- the packaged app stores uploads and outputs in `~/Library/Application Support/PDF Forge`
- OCR uses the installed Homebrew Tesseract on this Mac, for example `/opt/homebrew/bin/tesseract`
- the macOS build opens inside its own application window instead of launching your browser
- because the app is locally packaged and ad-hoc signed, macOS may still ask you to confirm opening it the first time

## Installer Downloads

Ready-to-download installers are organized in the [`installers/`](installers) folder.

- GitHub release: `https://github.com/aswathraj/pdf-toolkit-web/releases/tag/v1.0.0`
- macOS: tracked in the repo as `installers/mac/PDFForge-macOS.dmg` and also published in the release
- Windows: listed in `installers/windows/README.md` and published in the release as `PDFForgeSetup.exe`

## Windows EXE Build

You cannot produce a real Windows `.exe` from this macOS environment directly with PyInstaller. The project now includes the Windows build files so you can generate it on a Windows machine.

Files added for Windows packaging:

- `desktop_launcher.py`: starts the local server and opens the app in the default browser
- `pdf_forge.spec`: PyInstaller spec for a windowed executable
- `build_windows.bat`: one-command Windows build script
- `requirements-windows-build.txt`: Windows build-only dependency list

On Windows:

```bat
cd path\to\pdf_toolkit_web
build_windows.bat
```

That produces:

```text
dist\PDFForge.exe
```

## Windows Installer Build

The project now also includes a proper Windows installer definition built with Inno Setup.

Files added for installer packaging:

- `build_windows_installer.bat`: builds the portable EXE and the installer EXE
- `pdf_forge_installer.iss`: Inno Setup installer definition
- `scripts/prepare_tesseract.ps1`: bundles Tesseract into the app build
- `scripts/ensure_inno_setup.ps1`: installs Inno Setup if missing
- `.github/workflows/build-windows-installer.yml`: GitHub Actions workflow to build the installer on a Windows runner

On Windows:

```bat
cd path\to\pdf_toolkit_web
build_windows_installer.bat
```

That produces:

```text
installer_output\PDFForgeSetup.exe
```

The installer:

- installs `PDFForge.exe` into `%LOCALAPPDATA%\Programs\PDF Forge`
- creates Start Menu and optional desktop shortcuts
- launches the app after install
- includes OCR runtime when Tesseract is bundled during the build

## OCR In The Windows EXE / Installer

For OCR support in Windows, either:

- let the Windows build scripts install and bundle Tesseract automatically, or
- install Tesseract globally so `tesseract.exe` is on `PATH`, or
- place a `tesseract` folder beside the project before building so the spec bundles it into the executable

The packaged app stores uploads and outputs in the user data folder instead of the executable directory.
