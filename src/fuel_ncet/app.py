import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from fuel_ncet.gui.main_window import MainWindow
from fuel_ncet.util.resources import resource_path


def _set_windows_app_id():
    """Чтобы в панели задач была иконка приложения, а не python.exe (Windows)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            app_id = "fuel-ncet.app"  # можно любое уникальное строковое значение
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


def run():
    _set_windows_app_id()

    app = QApplication([])

    icon_path = resource_path("assets/app.ico")
    app.setWindowIcon(QIcon(str(icon_path)))

    w = MainWindow()
    # на всякий случай задаём и окну тоже
    w.setWindowIcon(QIcon(str(icon_path)))

    w.show()
    app.exec()