@echo off
setlocal

set SCRIPT_DIR=%~dp0

echo === MusicPlayer Android APK Wizard ===
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_android_wizard.ps1"
set ERR=%ERRORLEVEL%

if not "%ERR%"=="0" (
  echo.
  echo Wizard failed with exit code %ERR%.
)

echo.
pause
exit /b %ERR%
