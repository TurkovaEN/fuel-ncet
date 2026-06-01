import sys
from pathlib import Path

# чтобы работало при запуске из терминала: python main.py
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fuel_ncet.app import run

if __name__ == "__main__":
    run()