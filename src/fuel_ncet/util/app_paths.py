from __future__ import annotations

from pathlib import Path
import sys


def get_base_dir() -> Path:
    """
    В режиме .exe: папка рядом с exe
    В режиме разработки: корень проекта
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def get_cache_dir() -> Path:
    d = get_base_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d