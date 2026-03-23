$ErrorActionPreference = "Stop"

$compilerCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
) | Where-Object { $_ -and (Test-Path $_) }

if ($compilerCandidates.Count -gt 0) {
    Write-Host "Inno Setup already present at: $($compilerCandidates[0])"
    exit 0
}

if (Get-Command iscc.exe -ErrorAction SilentlyContinue) {
    Write-Host "Inno Setup compiler already available in PATH."
    exit 0
}

if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
    winget install --exact --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements --silent
}
elseif (Get-Command choco.exe -ErrorAction SilentlyContinue) {
    choco install innosetup -y --no-progress
}
else {
    throw "Neither winget nor choco is available to install Inno Setup automatically."
}

Write-Host "Inno Setup installation finished."
