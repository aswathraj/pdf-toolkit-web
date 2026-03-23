# Windows Installer

The Windows installer was built successfully on GitHub Actions and is available from this workflow run:

- [Build Windows Installer run 23455837808](https://github.com/aswathraj/pdf-toolkit-web/actions/runs/23455837808)

On that page, download the artifact named `PDFForge-Windows`. After extracting it, run:

- `PDFForgeSetup.exe` to install the app
- `PDFForge.exe` if you want the portable executable instead of the installer

Why the installer is not committed directly into this Git folder:

- the Windows build artifact is much larger than GitHub's normal repo file-size limit
- storing it as an Actions artifact avoids broken pushes and keeps the repo usable
