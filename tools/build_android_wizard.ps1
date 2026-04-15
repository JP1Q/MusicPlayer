param(
    [string]$Distro = "Ubuntu",
    [switch]$SkipApt
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Cyan
}

function Find-Distro {
    param([string]$PreferredName)

    $all = (& wsl -l -q) | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
    if (-not $all) {
        throw "No WSL distro found. Install Ubuntu first: wsl --install -d Ubuntu"
    }

    $match = $all | Where-Object { $_ -eq $PreferredName } | Select-Object -First 1
    if (-not $match) {
        $match = $all | Where-Object { $_ -like "$PreferredName*" } | Select-Object -First 1
    }

    if (-not $match) {
        Write-Host "[!] Preferred distro '$PreferredName' was not found." -ForegroundColor Yellow
        Write-Host "[i] Available distros: $($all -join ', ')" -ForegroundColor Yellow
        $match = $all | Select-Object -First 1
        Write-Host "[i] Using '$match'." -ForegroundColor Yellow
    }

    return $match
}

Write-Host "=== MusicPlayer Android APK Wizard (Windows + WSL) ===" -ForegroundColor Green

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    throw "WSL is not available on this machine. Install it with: wsl --install -d Ubuntu"
}

$repoRootWin = Split-Path -Parent $PSScriptRoot
$selectedDistro = Find-Distro -PreferredName $Distro

Write-Step "Using WSL distro: $selectedDistro"
Write-Step "Windows repo path: $repoRootWin"

$repoRootWsl = (& wsl -d $selectedDistro -- wslpath -a "$repoRootWin").Trim()
if (-not $repoRootWsl) {
    throw "Could not convert repository path to WSL path."
}

Write-Step "WSL repo path: $repoRootWsl"
Write-Host ""
Write-Host "This will build a DEBUG APK using Buildozer in WSL." -ForegroundColor DarkGray
if (-not $SkipApt) {
    Write-Host "It may ask for your Linux password for apt install." -ForegroundColor DarkGray
}

$confirm = Read-Host "Continue? (Y/N)"
if ($confirm -notin @("y", "Y", "yes", "YES")) {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

$aptStep = if ($SkipApt) {
    "echo 'Skipping apt install (--SkipApt)';"
} else {
    "sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3 python3-venv python3-pip;"
}

$bashScript = @"
set -euo pipefail
cd "$repoRootWsl"
$aptStep
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install buildozer==1.5.0 cython==0.29.37
chmod +x ./tools/build_android.sh
./tools/build_android.sh
"@

Write-Step "Running Android build pipeline in WSL..."
& wsl -d $selectedDistro -- bash -lc $bashScript

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "APK should be in: $repoRootWin\build_workspace\out\android" -ForegroundColor Green
