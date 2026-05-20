#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

VENV_PYTHON=".venv/bin/python"

if [ ! -f "requirements.txt" ]; then
    echo "requirements.txt was not found in $PROJECT_ROOT" >&2
    exit 1
fi

if [ ! -x "$VENV_PYTHON" ]; then
    if [ -e ".venv" ]; then
        echo ".venv exists, but .venv/bin/python was not found. Remove the incompatible .venv and run this script again." >&2
        exit 1
    fi

    if command -v python3.11 >/dev/null 2>&1; then
        python3.11 -m venv .venv
    elif command -v python3 >/dev/null 2>&1; then
        python3 -m venv .venv
    elif command -v python >/dev/null 2>&1; then
        python -m venv .venv
    else
        echo "Could not find Python. Install Python 3.11+ or make it available as python3.11, python3, or python." >&2
        exit 1
    fi
fi

"$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
    echo ".venv must use Python 3.11+. Remove .venv and recreate it with Python 3.11 or newer." >&2
    exit 1
}

"$VENV_PYTHON" -m pip install -r requirements.txt
"$VENV_PYTHON" -m playwright install chromium

echo
echo "Setup complete."
echo "Activate with: . .venv/bin/activate"
echo "Run with:      .venv/bin/python main.py"
