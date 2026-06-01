from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QFormLayout,
    QLineEdit, QDateEdit, QMessageBox, QCheckBox, QSpinBox, QLabel
)

from fuel_ncet.core.calc import CalcInput, calc
from fuel_ncet.util.formatting import parse_decimal_ru, fmt_money, fmt_decimal


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuel NCET")
        self.resize(1100, 700)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # ---------- Form ----------
        form = QFormLayout()
        layout.addLayout(form)

        self.date_state = QDateEdit()
        self.date_state.setCalendarPopup(True)
        self.date_state.setDisplayFormat("dd.MM.yyyy")
        self.date_state.setDate(QDate.currentDate())
        form.addRow("Дата состояния цен (Росстат):", self.date_state)

        self.price_ai92 = QLineEdit()
        self.price_ai95 = QLineEdit()
        self.price_dt_summer = QLineEdit()
        self.price_dt_winter = QLineEdit()

        self.price_ai92.setPlaceholderText("например 60,23")
        self.price_ai95.setPlaceholderText("например 63,38")
        self.price_dt_summer.setPlaceholderText("например 78,55")
        self.price_dt_winter.setPlaceholderText("если как лето — можно повторить")

        form.addRow("АИ-92 (Барнаул), руб:", self.price_ai92)
        form.addRow("АИ-95 (Барнаул), руб:", self.price_ai95)
        form.addRow("ДТ лето (Барнаул), руб:", self.price_dt_summer)
        form.addRow("ДТ зима (Барнаул), руб:", self.price_dt_winter)

        self.inflation_percent = QLineEdit()
        self.inflation_percent.setPlaceholderText("например 104,0")
        form.addRow("Годовой индекс прогнозной инфляции, %:", self.inflation_percent)

        # ---------- Degrees manual override ----------
        self.manual_degrees = QCheckBox("Править степени вручную (n_start, n_end)")
        layout.addWidget(self.manual_degrees)

        deg_row = QHBoxLayout()
        layout.addLayout(deg_row)

        deg_row.addWidget(QLabel("n_start:"))
        self.n_start = QSpinBox()
        self.n_start.setRange(0, 24)
        self.n_start.setEnabled(False)
        deg_row.addWidget(self.n_start)

        deg_row.addWidget(QLabel("n_end:"))
        self.n_end = QSpinBox()
        self.n_end.setRange(0, 24)
        self.n_end.setEnabled(False)
        deg_row.addWidget(self.n_end)

        deg_row.addStretch(1)

        self.manual_degrees.toggled.connect(self.n_start.setEnabled)
        self.manual_degrees.toggled.connect(self.n_end.setEnabled)

        # ---------- Buttons ----------
        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)

        self.btn_fetch = QPushButton("Загрузить с Росстата")
        self.btn_calc = QPushButton("Рассчитать")
        self.btn_export = QPushButton("Сохранить DOCX")

        btn_row.addWidget(self.btn_fetch)
        btn_row.addWidget(self.btn_calc)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)

        # ---------- Table preview ----------
        self.table = QTableWidget(4, 7)
        self.table.setHorizontalHeaderLabels([
            "№", "Наименование товара", "Ед. изм.", "Кол-во",
            "Цена Росстат (Барнаул)", "ИПЦ", "Начальная сумма"
        ])
        layout.addWidget(self.table)

        self._fill_static_rows()

        # Handlers
        self.btn_fetch.clicked.connect(self._not_ready_fetch)
        self.btn_calc.clicked.connect(self.on_calc)
        self.btn_export.clicked.connect(self._not_ready_export)

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

    def on_calc(self):
        try:
            # Если зима не заполнена — по умолчанию приравниваем к лету
            if not self.price_dt_winter.text().strip() and self.price_dt_summer.text().strip():
                self.price_dt_winter.setText(self.price_dt_summer.text().strip())

            qdate = self.date_state.date()
            base_month = qdate.month()

            inflation_percent = parse_decimal_ru(self.inflation_percent.text())  # 104,0
            inflation_factor = Decimal("1") + (inflation_percent - Decimal("100")) / Decimal("100")  # 1.040

            inp = CalcInput(
                base_month=base_month,
                inflation_year_factor=inflation_factor,
                price_ai92=parse_decimal_ru(self.price_ai92.text()),
                price_ai95=parse_decimal_ru(self.price_ai95.text()),
                price_dt_summer=parse_decimal_ru(self.price_dt_summer.text()),
                price_dt_winter=parse_decimal_ru(self.price_dt_winter.text()),
                manual_degrees=self.manual_degrees.isChecked(),
                n_start=int(self.n_start.value()),
                n_end=int(self.n_end.value()),
            )

            out = calc(inp)

            # если авто-режим, покажем рассчитанные степени в полях
            if not self.manual_degrees.isChecked():
                self.n_start.setValue(out.n_start)
                self.n_end.setValue(out.n_end)

            prices = [inp.price_ai92, inp.price_ai95, inp.price_dt_summer, inp.price_dt_winter]
            sums = [out.sum_ai92, out.sum_ai95, out.sum_dt_summer, out.sum_dt_winter]

            for r in range(4):
                self.table.setItem(r, 4, QTableWidgetItem(fmt_money(prices[r])))
                self.table.setItem(r, 5, QTableWidgetItem(fmt_decimal(out.ipc_period, 2)))
                self.table.setItem(r, 6, QTableWidgetItem(fmt_money(sums[r])))

            QMessageBox.information(
                self,
                "Расчёт выполнен",
                "Промежуточные значения:\n"
                f"Ежемесячный индекс (m): {fmt_decimal(out.monthly_index, 4)}\n"
                f"Степени: n_start={out.n_start}, n_end={out.n_end}\n"
                f"Дефлятор начало: {fmt_decimal(out.deflator_start, 4)}\n"
                f"Дефлятор конец: {fmt_decimal(out.deflator_end, 4)}\n"
                f"ИПЦ период: {fmt_decimal(out.ipc_period, 2)}\n"
                f"Итого: {fmt_money(out.total_sum)}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _not_ready_fetch(self):
        QMessageBox.information(self, "Инфо", "Загрузка с Росстата будет в следующем этапе.")

    def _not_ready_export(self):
        QMessageBox.information(self, "Инфо", "Экспорт DOCX будет в следующем этапе.")