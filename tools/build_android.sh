#!/usr/bin/env bash
set -euo pipefail

# Build a debug APK using buildozer (run inside WSL/Linux).
#
# Usage (WSL):
#   cd /mnt/d/PythonShit/UkasCoUmis
#   chmod +x ./tools/build_android.sh
#   ./tools/build_android.sh

if ! command -v buildozer >/dev/null 2>&1; then
  # buildozer may be installed but its scripts dir (usually ~/.local/bin) might not be on PATH.
  # Prefer running it as a Python module so PATH is irrelevant.
  :
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
  echo "  python -m pip install buildozer cython" >&2
  echo >&2
  echo "If you installed with --user, ensure ~/.local/bin is on PATH:" >&2
  echo "  export PATH=\"$HOME/.local/bin:$PATH\"" >&2
  exit 1
fi

"$PYTHON" -m buildozer -v android debug

echo
echo "APK should be in ./bin/"


