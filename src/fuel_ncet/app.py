import os
import sys
from pathlib import Path

import PySide2
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication

from fuel_ncet.gui.main_window import MainWindow
from fuel_ncet.util.resources import resource_path


def _set_windows_app_id():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("fuel-ncet.legacy")
        except Exception:
            pass


def _fix_qt_plugin_path():
    pyside_dir = Path(PySide2.__file__).resolve().parent
    plugins_dir = pyside_dir / "plugins"
    os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins_dir / "platforms")


def run():
    _set_windows_app_id()
    _fix_qt_plugin_path()

    app = QApplication([])

    icon_path = resource_path("assets/app.ico")
    app.setWindowIcon(QIcon(str(icon_path)))

    w = MainWindow()
    w.setWindowIcon(QIcon(str(icon_path)))
    w.show()

    app.exec_()