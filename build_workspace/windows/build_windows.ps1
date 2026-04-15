param(
  [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"

Write-Host "== UkasCoUmis Windows build ==" -ForegroundColor Cyan

Push-Location $PSScriptRoot
try {
  $rootBuildScript = Resolve-Path "..\..\tools\build_windows.ps1"
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
