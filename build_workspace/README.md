# build_workspace

Tahle složka je schválně bokem, aby se build soubory nemíchaly do rootu projektu.

## Windows (EXE)

Standard release flow:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1 -BuildInstaller
```

Výstup je v `build_workspace\out\`:
- `dist\UkasCoUmis\...`
- `release\UkasCoUmis-windows-portable.zip`
- `release\UkasCoUmis-Setup.exe`

Wrapper script stále funguje:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_workspace\windows\build_windows.ps1 -BuildInstaller
```

## Android (APK)

Buildozer se typicky pouští ve WSL/Linuxu. Doporučení:

```bash
cd /mnt/d/PythonShit/UkasCoUmis
buildozer android debug
```

`buildozer.spec` je v rootu.
