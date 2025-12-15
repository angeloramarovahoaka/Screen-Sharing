#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Optional: provide your venv path via VENV_PATH
# Example: VENV_PATH="$HOME/Documents/MISA/Mr Caraz/venv" ./run_app.sh
VENV_PATH_DEFAULT="$ROOT_DIR/venv"
VENV_PATH="${VENV_PATH:-$VENV_PATH_DEFAULT}"

if [[ -x "$VENV_PATH/bin/python" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_PATH/bin/activate"
  exec python main.py
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 main.py
fi

if command -v python >/dev/null 2>&1; then
  exec python main.py
fi

echo "ERROR: No python interpreter found. Install python3 or provide VENV_PATH." >&2
exit 127
