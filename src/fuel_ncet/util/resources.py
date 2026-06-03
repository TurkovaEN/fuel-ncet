from __future__ import annotations

from pathlib import Path
import sys


def resource_path(rel_path: str) -> Path:
    """
    Путь к ресурсу, который работает:
    - в режиме разработки (PyCharm)
    - в режиме собранного exe (PyInstaller, onefile)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # временная папка, куда PyInstaller распаковал ресурсы
    else:
        # .../src/fuel_ncet/util/resources.py -> корень проекта
        base = Path(__file__).resolve().parents[3]
    return base / rel_path