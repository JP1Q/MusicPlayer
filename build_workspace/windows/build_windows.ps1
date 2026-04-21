param(
  [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"

Write-Host "== UkasCoUmis Windows build ==" -ForegroundColor Cyan

Push-Location $PSScriptRoot
try {
  $rootBuildScriptPath = "..\..\tools\build_windows.ps1"
  if (-not (Test-Path $rootBuildScriptPath)) {
    Write-Host "[!] Root build script not found at $rootBuildScriptPath. Expected repository layout may be incorrect." -ForegroundColor Red
    exit 1
  }
  $rootBuildScript = Resolve-Path $rootBuildScriptPath
  $args = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $rootBuildScript,
    "-OutputRoot", "build_workspace\out"
  )
  if ($BuildInstaller) {
    $args += "-BuildInstaller"
  }
  & powershell @args | Out-Host
}
finally {
  Pop-Location
}
