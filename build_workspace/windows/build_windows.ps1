param(
  [string]$Python = "py -3.11",
  [string]$SpecPath = "..\..\UkasCoUmis.spec",
  [string]$ProjectRoot = "..\.."
)

$ErrorActionPreference = "Stop"

Write-Host "== UkasCoUmis Windows build ==" -ForegroundColor Cyan

Push-Location $PSScriptRoot
try {
  # ensure we run from build_workspace\windows and outputs go into build_workspace\out
  $OutRoot = Resolve-Path "..\out"
  $DistDir = Join-Path $OutRoot "dist"
  $WorkDir = Join-Path $OutRoot "pyinstaller-work"

  New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
  New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

  # install pyinstaller into the active venv (recommended) or into global python
  & powershell -NoProfile -Command "$Python -m pip install -U pyinstaller" | Out-Host

  # build
  & powershell -NoProfile -Command "$Python -m PyInstaller --noconfirm --clean --distpath `"$DistDir`" --workpath `"$WorkDir`" `"$SpecPath`"" | Out-Host

  Write-Host "Done. Check: $DistDir" -ForegroundColor Green
}
finally {
  Pop-Location
}

