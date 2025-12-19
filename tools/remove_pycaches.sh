#!/usr/bin/env bash
set -euo pipefail

ROOT="."
DELETE=0

usage() {
  echo "Usage: $0 [--root DIR] [--delete]"
  echo "  --root DIR   Root directory to scan (default: .)"
  echo "  --delete     Actually remove directories (default: dry-run)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --delete) DELETE=1; shift ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

echo "Scanning for __pycache__ under: $ROOT"
if [[ $DELETE -eq 0 ]]; then
  echo "Dry-run: found directories:"
  find "$ROOT" -type d -name "__pycache__" -print
  echo "Run with --delete to remove them."
  exit 0
fi

echo "Deleting __pycache__ directories..."
find "$ROOT" -type d -name "__pycache__" -print0 | xargs -0 -r rm -rf --
echo "Done."
