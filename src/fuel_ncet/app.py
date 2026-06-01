from PySide6.QtWidgets import QApplication
from fuel_ncet.gui.main_window import MainWindow


def run():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()