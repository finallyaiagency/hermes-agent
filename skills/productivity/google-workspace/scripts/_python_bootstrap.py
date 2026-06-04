"""Interpreter bootstrap helpers for Google Workspace skill scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _candidate_python_paths() -> list[Path]:
    """Return repo-local Python interpreters in preferred order."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[4]
    candidates = [
        repo_root / "venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / "venv" / "bin" / "python",
        repo_root / ".venv" / "bin" / "python",
    ]
    return [path for path in candidates if path.exists()]


def ensure_supported_interpreter(min_version: tuple[int, int] = (3, 11)) -> None:
    """Re-exec into the repo venv when the active Python is too old."""
    if sys.version_info >= min_version:
        return

    current = Path(sys.executable).resolve()
    for candidate in _candidate_python_paths():
        try:
            if candidate.resolve() == current:
                return
        except OSError:
            pass
        os.execv(str(candidate), [str(candidate), *sys.argv])
