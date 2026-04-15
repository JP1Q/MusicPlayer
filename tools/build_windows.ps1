param(
    [switch]$OneFile,
    [switch]$BuildInstaller,
    [string]$OutputRoot = "build_workspace\out"
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
$resolvedOutRoot = [System.IO.Path]::GetFullPath((Join-Path $root $OutputRoot))
$distPath = Join-Path $resolvedOutRoot "dist"
$workPath = Join-Path $resolvedOutRoot "pyinstaller-work"
$releasePath = Join-Path $resolvedOutRoot "release"

New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $releasePath | Out-Null

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
    "--distpath", $distPath,
    "--workpath", $workPath,
    $mode,
    "UkasCoUmis.spec"
) | Where-Object { $_ -and $_.ToString().Trim() -ne "" }

Write-Host "Running: $py $($argsList -join ' ')" -ForegroundColor Cyan
& $py @argsList | Out-Host

$appDistDir = Join-Path $distPath "UkasCoUmis"
if (-not (Test-Path $appDistDir)) {
    Write-Host "[!] Expected app output not found: $appDistDir" -ForegroundColor Red
    exit 1
}

$portableZip = Join-Path $releasePath "UkasCoUmis-windows-portable.zip"
if (Test-Path $portableZip) {
    Remove-Item $portableZip -Force
}
Compress-Archive -Path (Join-Path $appDistDir "*") -DestinationPath $portableZip

if ($BuildInstaller) {
    $issPath = Join-Path $root "tools\windows\installer.iss"
    if (-not (Test-Path $issPath)) {
        Write-Host "[!] Inno Setup script missing: $issPath" -ForegroundColor Red
        exit 1
    }

    $iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $iscc = Get-Command "ISCC" -ErrorAction SilentlyContinue
    }
    if (-not $iscc) {
        Write-Host "[!] Inno Setup compiler (ISCC) was not found on PATH. Install it with 'choco install innosetup -y' or from https://jrsoftware.org/isdl.php." -ForegroundColor Red
        exit 1
    }

    & $iscc.Path "/DSourceDir=$appDistDir" "/DOutputDir=$releasePath" $issPath | Out-Host
}

Write-Host "`nBuild complete. Dist: $appDistDir" -ForegroundColor Green
Write-Host "Portable package: $portableZip" -ForegroundColor Green
if ($BuildInstaller) {
    Write-Host "Installer output: $releasePath" -ForegroundColor Green
}
Write-Host "Tip: For full yt-dlp functionality inside the release, ship ffmpeg + ffprobe with the release zip." -ForegroundColor DarkGray

