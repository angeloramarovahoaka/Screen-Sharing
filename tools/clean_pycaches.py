"""
Utilities to remove __pycache__ directories.

Usage:
    from tools.clean_pycaches import clean_pycaches
    clean_pycaches(root=".")

This module is intentionally small and safe: it only removes directories
named "__pycache__" under the given root.
"""
from pathlib import Path
import shutil
from typing import List


def clean_pycaches(root: str = ".", dry_run: bool = False) -> List[Path]:
    """Recursively remove all `__pycache__` directories under `root`.

    Returns a list of Path objects that were removed.

    If `dry_run` is True, no deletion is performed and the list of
    candidate directories is returned.
    """
    root_path = Path(root).resolve()
    removed = []

    if not root_path.exists():
        return removed

    for p in root_path.rglob("__pycache__"):
        # Only target directories named exactly __pycache__
        if p.is_dir():
            removed.append(p)
            if not dry_run:
                try:
                    shutil.rmtree(p)
                except Exception:
                    # best-effort: skip directories we can't remove
                    pass

    return removed
