#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

# Build a debug APK using buildozer (run inside WSL/Linux).
#
# Usage (WSL):
#   cd /path/to/MusicPlayer
#   ./tools/build_android.sh

if [ "$(uname -s)" != "Linux" ]; then
  echo "Android APK build is supported only on Linux/WSL." >&2
  exit 1
fi

if ! command -v java >/dev/null 2>&1; then
  echo "Java not found. Install OpenJDK 17 before running this script." >&2
  exit 1
fi

PYTHON="python3"
if [ -x "./.venv/bin/python" ]; then
  PYTHON="./.venv/bin/python"
fi

if ! "$PYTHON" -c "import buildozer" >/dev/null 2>&1; then
  echo "Python module 'buildozer' not found for: $PYTHON" >&2
  echo "Install it in WSL (recommended: project venv):" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  . ./.venv/bin/activate" >&2
  echo "  python -m pip install -U pip" >&2
  echo "  python -m pip install buildozer==1.5.0 cython==0.29.37" >&2
  echo >&2
  echo "If you installed with --user, ensure ~/.local/bin is on PATH:" >&2
  echo "  export PATH=\"$HOME/.local/bin:$PATH\"" >&2
  exit 1
fi

"$PYTHON" -m buildozer -v android debug

APK_PATH="$(find "$ROOT_DIR/build_workspace/out/android" -maxdepth 1 -type f -name "*-debug*.apk" | sort | tail -n 1 || true)"

echo
if [ -n "$APK_PATH" ]; then
  echo "Debug APK artifact:"
  echo "  $APK_PATH"
else
  echo "Build completed but debug APK was not found in build_workspace/out/android." >&2
  echo "Check Buildozer output above for errors." >&2
  exit 1
fi
