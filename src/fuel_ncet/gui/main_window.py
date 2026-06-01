from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QFormLayout,
    QLineEdit, QDateEdit, QMessageBox, QCheckBox, QSpinBox
)
from PySide6.QtCore import QDate


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuel NCET")
        self.resize(1050, 650)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # --- Input form ---
        form = QFormLayout()
        layout.addLayout(form)

        self.date_state = QDateEdit()
        self.date_state.setCalendarPopup(True)
        self.date_state.setDate(QDate.currentDate())
        form.addRow("Дата состояния цен (Росстат):", self.date_state)

        self.price_ai92 = QLineEdit()
        self.price_ai95 = QLineEdit()
        self.price_dt_summer = QLineEdit()
        self.price_dt_winter = QLineEdit()
        form.addRow("АИ-92 (Барнаул), руб:", self.price_ai92)
        form.addRow("АИ-95 (Барнаул), руб:", self.price_ai95)
        form.addRow("ДТ лето (Барнаул), руб:", self.price_dt_summer)
        form.addRow("ДТ зима (Барнаул), руб:", self.price_dt_winter)

        self.inflation_percent = QLineEdit()
        self.inflation_percent.setPlaceholderText("Напр. 104,0")
        form.addRow("Годовой индекс прогнозной инфляции, %:", self.inflation_percent)

        # Manual degrees override
        self.manual_degrees = QCheckBox("Править степени вручную (n_start, n_end)")
        layout.addWidget(self.manual_degrees)

        row_deg = QHBoxLayout()
        self.n_start = QSpinBox()
        self.n_start.setRange(0, 24)
        self.n_end = QSpinBox()
        self.n_end.setRange(0, 24)

        self.n_start.setEnabled(False)
        self.n_end.setEnabled(False)

        row_deg.addWidget(self.n_start)
        row_deg.addWidget(self.n_end)
        layout.addLayout(row_deg)

        self.manual_degrees.toggled.connect(self.n_start.setEnabled)
        self.manual_degrees.toggled.connect(self.n_end.setEnabled)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)

        self.btn_fetch = QPushButton("Загрузить с Росстата")
        self.btn_calc = QPushButton("Рассчитать")
        self.btn_export = QPushButton("Сохранить DOCX")

        btn_row.addWidget(self.btn_fetch)
        btn_row.addWidget(self.btn_calc)
        btn_row.addWidget(self.btn_export)

        # --- Table preview ---
        self.table = QTableWidget(4, 7)
        self.table.setHorizontalHeaderLabels([
            "№", "Наименование товара", "Ед. изм.", "Кол-во",
            "Цена Росстат (Барнаул)", "ИПЦ", "Начальная сумма"
        ])
        layout.addWidget(self.table)

        self._fill_static_rows()

        # temporary handlers
        self.btn_fetch.clicked.connect(self._not_ready)
        self.btn_calc.clicked.connect(self._not_ready)
        self.btn_export.clicked.connect(self._not_ready)

    def _fill_static_rows(self):
        items = [
            (1, "Бензин автомобильный (розничная реализация) АИ-92"),
            (2, "Бензин автомобильный (розничная реализация) АИ-95"),
            (3, "Топливо дизельное (розничная реализация) (летний период)"),
            (4, "Топливо дизельное (розничная реализация) (зимний период)"),
        ]
        for r, (num, name) in enumerate(items):
            self.table.setItem(r, 0, QTableWidgetItem(str(num)))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.setItem(r, 2, QTableWidgetItem("Литр; кубический дециметр"))
            self.table.setItem(r, 3, QTableWidgetItem("1"))

    def _not_ready(self):
        QMessageBox.information(self, "Инфо", "Этот шаг будет реализован в следующих коммитах.")