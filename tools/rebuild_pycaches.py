"""
Small CLI utility to remove all `__pycache__` directories and optionally
recompile Python files under a project root.

Usage examples:
    python tools/rebuild_pycaches.py --clean --compile
    python tools/rebuild_pycaches.py --clean --root mypackage
    python tools/rebuild_pycaches.py --clean --dry-run

This file uses `tools.clean_pycaches.clean_pycaches` (already present)
and `compileall` to (re)generate .pyc files.
"""
import argparse
import sys
from pathlib import Path
import compileall

from tools.clean_pycaches import clean_pycaches


def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = argparse.ArgumentParser(description="Clean __pycache__ folders and optionally compile Python files")
    parser.add_argument("--clean", action="store_true", help="Remove all __pycache__ directories under the root")
    parser.add_argument("--compile", action="store_true", help="(Re)compile .py files to .pyc after cleaning")
    parser.add_argument("--root", type=str, default='.', help="Root folder to operate on (default: project root)")
    parser.add_argument("--dry-run", action="store_true", help="When cleaning, only list candidates without deleting")
    parser.add_argument("--force", action="store_true", help="Force recompilation even if .pyc is up-to-date (passed to compileall)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root path does not exist: {root}")
        return 2

    if args.clean:
        print(f"🧹 Cleaning __pycache__ under: {root}")
        removed = clean_pycaches(root=str(root), dry_run=args.dry_run)
        if args.dry_run:
            if removed:
                print("Found the following __pycache__ directories:")
                for p in removed:
                    print(f"- {p}")
            else:
                print("No __pycache__ found.")
        else:
            if removed:
                print("Removed the following directories:")
                for p in removed:
                    print(f"- {p}")
            else:
                print("No __pycache__ found.")

    if args.compile:
        print(f"⚙️  Compiling Python files under: {root} (force={args.force})")
        # compileall returns True if successful
        ok = compileall.compile_dir(str(root), force=args.force, quiet=1)
        if ok:
            print("✅ Compilation finished.")
        else:
            print("⚠️ Compilation reported errors (see output).")

    if not args.clean and not args.compile:
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
