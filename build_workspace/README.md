# build_workspace

Tahle složka je schválně bokem, aby se build soubory nemíchaly do rootu projektu.

## Windows (EXE)

Použij skript `windows_build.ps1` (přidá se později) nebo:

```powershell
py -3.11 -m pip install pyinstaller
py -3.11 -m PyInstaller --clean --noconfirm ..\UkasCoUmis.spec
```

Výstup bude v `..\dist\` (PyInstaller default).

## Android (APK)

Buildozer se typicky pouští ve WSL/Linuxu. Doporučení:

```bash
cd /mnt/d/PythonShit/UkasCoUmis
buildozer android debug
```

`buildozer.spec` je v rootu.

