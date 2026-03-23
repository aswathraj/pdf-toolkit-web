param(
    [switch]$InstallIfMissing
)

$ErrorActionPreference = "Stop"

function Find-TesseractRoot {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Tesseract-OCR"),
        (Join-Path ${env:ProgramFiles(x86)} "Tesseract-OCR"),
        (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR")
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate "tesseract.exe")) {
            return $candidate
        }
    }

    $command = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($command) {
        return Split-Path -Parent $command.Source
    }

    return $null
}

function Install-TesseractIfNeeded {
    if (Find-TesseractRoot) {
        return
    }

    if (-not $InstallIfMissing) {
        throw "Tesseract was not found. Install it first or rerun this script with -InstallIfMissing."
    }

    if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
        winget install --exact --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements --silent
    }
    elseif (Get-Command choco.exe -ErrorAction SilentlyContinue) {
        choco install tesseract -y --no-progress
    }
    else {
        throw "Neither winget nor choco is available to install Tesseract automatically."
    }
}

Install-TesseractIfNeeded

$sourceRoot = Find-TesseractRoot
if (-not $sourceRoot) {
    throw "Tesseract could not be located after installation."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$bundleRoot = Join-Path $projectRoot "tesseract"

if (Test-Path $bundleRoot) {
    Remove-Item $bundleRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $bundleRoot | Out-Null
Copy-Item (Join-Path $sourceRoot "*") $bundleRoot -Recurse -Force

Write-Host "Bundled Tesseract from: $sourceRoot"
Write-Host "Bundle output: $bundleRoot"
