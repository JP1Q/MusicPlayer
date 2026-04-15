param(
    [switch]$OneFile
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[!] .venv not found. Create it first: python -m venv .venv" -ForegroundColor Yellow
}

# Use venv python if available
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

& $py -m pip install --upgrade pip | Out-Host
& $py -m pip install -r requirements.txt | Out-Host
& $py -m pip install pyinstaller | Out-Host

$mode = if ($OneFile) { "--onefile" } else { "" }

# NOTE: --add-data uses ';' on Windows
# Build from the spec so we auto-include everything defined there (e.g. all *.png assets).
if (-not (Test-Path "UkasCoUmis.spec")) {
    Write-Host "[!] UkasCoUmis.spec not found. Run this once to generate it:" -ForegroundColor Yellow
    Write-Host "    $py -m PyInstaller --name UkasCoUmis --windowed main.py" -ForegroundColor Yellow
    exit 1
}

$argsList = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    $mode,
    "UkasCoUmis.spec"
) | Where-Object { $_ -and $_.ToString().Trim() -ne "" }

Write-Host "Running: $py $($argsList -join ' ')" -ForegroundColor Cyan
& $py @argsList | Out-Host

Write-Host "\nBuild complete. Output is in ./dist" -ForegroundColor Green
Write-Host "Tip: For full yt-dlp functionality inside the release, ship ffmpeg + ffprobe with the release zip." -ForegroundColor DarkGray



