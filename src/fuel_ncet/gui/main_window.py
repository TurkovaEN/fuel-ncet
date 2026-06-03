from decimal import Decimal
from datetime import date as dt_date
from pathlib import Path
import shutil

from PySide6.QtCore import QDate, QObject, QThread, Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QFormLayout,
    QLineEdit, QDateEdit, QMessageBox, QCheckBox, QSpinBox, QLabel,
    QFileDialog
)

from fuel_ncet.core.calc import CalcInput, calc
from fuel_ncet.providers.rosstat import fetch_latest_prices
from fuel_ncet.util.app_paths import get_cache_dir
from fuel_ncet.util.formatting import parse_decimal_ru, fmt_money, fmt_decimal
from fuel_ncet.util.ru_money import money_to_words
from fuel_ncet.export.docx_exporter import ExportData, export_docx, MONTHS_RU_NOM


INVALID_STYLE = "border: 2px solid #cc0000;"
VALID_STYLE = ""


class RosstatWorker(QObject):
    loaded = Signal(object)    # RosstatPrices
    error = Signal(str)
    done = Signal()

    def __init__(self, as_of: dt_date, cache_dir: Path):
        super().__init__()
        self.as_of = as_of
        self.cache_dir = cache_dir

    def run(self):
        try:
            data = fetch_latest_prices(as_of=self.as_of, cache_dir=self.cache_dir)
            self.loaded.emit(data)
        except Exception as e:
            msg = str(e).strip() or repr(e)
            self.error.emit(msg)
        finally:
            self.done.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuel NCET")
        self.resize(1120, 860)

        self.cache_dir = get_cache_dir()

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        form = QFormLayout()
        layout.addLayout(form)

        self.date_doc = QDateEdit()
        self.date_doc.setCalendarPopup(True)
        self.date_doc.setDisplayFormat("dd.MM.yyyy")
        self.date_doc.setDate(QDate.currentDate())
        form.addRow("Дата формирования (подготовки):", self.date_doc)

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

        self.max_contract_price = QLineEdit()
        self.max_contract_price.setPlaceholderText("например 748 876,00")
        form.addRow("Максимальное значение цены контракта, руб:", self.max_contract_price)

        self.chk_clear_cache = QCheckBox("Очищать кэш при выходе")
        self.chk_clear_cache.setChecked(True)
        layout.addWidget(self.chk_clear_cache)

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

        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)

        self.btn_fetch = QPushButton("Загрузить с Росстата (по дате формирования)")
        self.btn_reset = QPushButton("Сброс")
        self.btn_calc = QPushButton("Рассчитать")
        self.btn_export = QPushButton("Сохранить DOCX")

        btn_row.addWidget(self.btn_fetch)
        btn_row.addWidget(self.btn_reset)
        btn_row.addWidget(self.btn_calc)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

        self.table = QTableWidget(5, 7)
        self.table.setHorizontalHeaderLabels([
            "№", "Наименование товара", "Ед. изм.", "Кол-во",
            "Цена Росстат (Барнаул)", "ИПЦ", "Начальная сумма"
        ])
        layout.addWidget(self.table)

        self._fill_static_rows()

        # Валидация + форматирование
        self._setup_validators()

        # handlers
        self.btn_fetch.clicked.connect(self.on_fetch_rosstat)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_calc.clicked.connect(self.on_calc)
        self.btn_export.clicked.connect(self.on_export_docx)

        self._last_calc_out = None
        self._last_calc_inp = None

        self._rosstat_thread: QThread | None = None
        self._rosstat_worker: RosstatWorker | None = None

    # ------------------- validation helpers -------------------
    def _mark_valid(self, w: QLineEdit):
        w.setStyleSheet(VALID_STYLE)

    def _mark_invalid(self, w: QLineEdit):
        w.setStyleSheet(INVALID_STYLE)

    def _setup_validators(self):
        # Цена: цифры + (запятая/точка) + до 2 знаков
        rx_money = QRegularExpression(r"^\d+(?:[,.]\d{0,2})?$")
        v_money = QRegularExpressionValidator(rx_money, self)

        # ИПЦ (%): цифры + (запятая/точка) + до 2 знаков (потом форматируем до 1)
        rx_percent = QRegularExpression(r"^\d+(?:[,.]\d{0,2})?$")
        v_percent = QRegularExpressionValidator(rx_percent, self)

        # Макс. цена: разрешаем пробелы как разделитель тысяч
        # примеры: 748 876,00 / 748876,00 / 748876
        rx_max = QRegularExpression(r"^(?:\d{1,3}(?: \d{3})+|\d+)(?:[,.]\d{0,2})?$")
        v_max = QRegularExpressionValidator(rx_max, self)

        for w in (self.price_ai92, self.price_ai95, self.price_dt_summer, self.price_dt_winter):
            w.setValidator(v_money)
            w.textChanged.connect(lambda _=None, ww=w: self._mark_valid(ww))
            w.editingFinished.connect(lambda ww=w: self._format_money_field(ww, decimals=2, group=False))

        self.inflation_percent.setValidator(v_percent)
        self.inflation_percent.textChanged.connect(lambda _=None: self._mark_valid(self.inflation_percent))
        self.inflation_percent.editingFinished.connect(self._format_percent_field)

        self.max_contract_price.setValidator(v_max)
        self.max_contract_price.textChanged.connect(lambda _=None: self._mark_valid(self.max_contract_price))
        self.max_contract_price.editingFinished.connect(self._format_max_contract_field)

    def _format_money_field(self, w: QLineEdit, decimals: int = 2, group: bool = False):
        t = w.text().strip()
        if not t:
            return
        try:
            val = parse_decimal_ru(t)
            if val < 0:
                raise ValueError("Число не может быть отрицательным")
            if group:
                # 748 876,00
                s = f"{val:,.{decimals}f}".replace(",", " ").replace(".", ",")
            else:
                s = f"{val:.{decimals}f}".replace(".", ",")
            w.setText(s)
            self._mark_valid(w)
        except Exception:
            self._mark_invalid(w)

    def _format_percent_field(self):
        t = self.inflation_percent.text().strip()
        if not t:
            return
        try:
            val = parse_decimal_ru(t)
            if val <= 0:
                raise ValueError("ИПЦ должен быть > 0")
            # формат до 1 знака: 104,0
            s = f"{val:.1f}".replace(".", ",")
            self.inflation_percent.setText(s)
            self._mark_valid(self.inflation_percent)
        except Exception:
            self._mark_invalid(self.inflation_percent)

    def _format_max_contract_field(self):
        self._format_money_field(self.max_contract_price, decimals=2, group=True)

    def _collect_required_decimals_for_calc(self):
        errors = []

        def need(w: QLineEdit, title: str) -> Decimal | None:
            txt = w.text().strip()
            if not txt:
                self._mark_invalid(w)
                errors.append(f"{title} (пусто)")
                return None
            try:
                v = parse_decimal_ru(txt)
                if v < 0:
                    raise ValueError()
                self._mark_valid(w)
                return v
            except Exception:
                self._mark_invalid(w)
                errors.append(f"{title} (неверный формат)")
                return None

        vals = {
            "ai92": need(self.price_ai92, "АИ-92"),
            "ai95": need(self.price_ai95, "АИ-95"),
            "dt_s": need(self.price_dt_summer, "ДТ лето"),
            "dt_w": need(self.price_dt_winter, "ДТ зима"),
            "infl": need(self.inflation_percent, "ИПЦ (годовой индекс, %)"),
        }

        if any(v is None for v in vals.values()):
            QMessageBox.critical(
                self,
                "Ошибка ввода",
                "Исправьте поля:\n- " + "\n- ".join(errors)
            )
            return None

        return vals  # type: ignore[return-value]

    def _collect_required_decimals_for_export(self):
        errors = []

        def need(w: QLineEdit, title: str) -> Decimal | None:
            txt = w.text().strip()
            if not txt:
                self._mark_invalid(w)
                errors.append(f"{title} (пусто)")
                return None
            try:
                v = parse_decimal_ru(txt)
                if v < 0:
                    raise ValueError()
                self._mark_valid(w)
                return v
            except Exception:
                self._mark_invalid(w)
                errors.append(f"{title} (неверный формат)")
                return None

        max_price = need(self.max_contract_price, "Максимальная цена контракта")
        if max_price is None:
            QMessageBox.critical(
                self,
                "Ошибка ввода",
                "Исправьте поля:\n- " + "\n- ".join(errors)
            )
            return None
        return max_price

    # ------------------- window / caching -------------------
    def closeEvent(self, event):
        if self._rosstat_thread is not None and self._rosstat_thread.isRunning():
            self._rosstat_thread.quit()
            self._rosstat_thread.wait(5000)

        if self.chk_clear_cache.isChecked():
            try:
                if self.cache_dir.exists():
                    shutil.rmtree(self.cache_dir, ignore_errors=True)
            except Exception:
                pass

        super().closeEvent(event)

    def _set_busy(self, busy: bool):
        self.btn_fetch.setEnabled(not busy)
        self.btn_reset.setEnabled(not busy)
        self.btn_calc.setEnabled(not busy)
        self.btn_export.setEnabled(not busy)
        self.btn_fetch.setText("Загрузка..." if busy else "Загрузить с Росстата (по дате формирования)")

    def _fill_static_rows(self):
        self.table.clearContents()
        self.table.setRowCount(5)

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

        total_row = 4
        self.table.setSpan(total_row, 0, 1, 6)
        self.table.setItem(total_row, 0, QTableWidgetItem("Итого"))

    def on_reset(self):
        today = QDate.currentDate()
        self.date_doc.setDate(today)
        self.date_state.setDate(today)

        for w in (
            self.price_ai92, self.price_ai95, self.price_dt_summer, self.price_dt_winter,
            self.inflation_percent, self.max_contract_price
        ):
            w.clear()
            self._mark_valid(w)

        self.manual_degrees.setChecked(False)
        self.n_start.setValue(0)
        self.n_end.setValue(0)

        self.lbl_status.setText("")
        self._fill_static_rows()

        self._last_calc_out = None
        self._last_calc_inp = None

    # -------- ROSSTAT (в фоне) --------
    def on_fetch_rosstat(self):
        if self._rosstat_thread is not None and self._rosstat_thread.isRunning():
            return

        qd = self.date_doc.date()
        as_of = dt_date(qd.year(), qd.month(), qd.day())

        self.lbl_status.setText("Загрузка данных Росстата...")
        self._set_busy(True)

        self._rosstat_thread = QThread(self)
        self._rosstat_worker = RosstatWorker(as_of=as_of, cache_dir=self.cache_dir)
        self._rosstat_worker.moveToThread(self._rosstat_thread)

        self._rosstat_thread.started.connect(self._rosstat_worker.run)
        self._rosstat_worker.loaded.connect(self._on_rosstat_loaded)
        self._rosstat_worker.error.connect(self._on_rosstat_error)
        self._rosstat_worker.done.connect(self._rosstat_thread.quit)
        self._rosstat_thread.finished.connect(self._on_rosstat_finished)

        self._rosstat_thread.start()

    def _on_rosstat_loaded(self, data):
        self.date_state.setDate(QDate(data.date_state.year, data.date_state.month, data.date_state.day))

        self.price_ai92.setText(f"{data.ai92_barnaul:.2f}".replace(".", ","))
        self.price_ai95.setText(f"{data.ai95_barnaul:.2f}".replace(".", ","))
        self.price_dt_summer.setText(f"{data.diesel_barnaul:.2f}".replace(".", ","))
        self.price_dt_winter.setText(f"{data.diesel_barnaul:.2f}".replace(".", ","))

        for w in (self.price_ai92, self.price_ai95, self.price_dt_summer, self.price_dt_winter):
            self._format_money_field(w, decimals=2, group=False)

        ssl_insecure = bool(getattr(data, "ssl_insecure_used", False))
        if ssl_insecure:
            self.lbl_status.setText(f"Росстат загружен: {data.date_state.strftime('%d.%m.%Y')} (SSL без проверки)")
        else:
            self.lbl_status.setText(f"Росстат загружен: {data.date_state.strftime('%d.%m.%Y')}")

    def _on_rosstat_error(self, msg: str):
        self.lbl_status.setText("Ошибка загрузки Росстата.")
        QMessageBox.critical(self, "Ошибка загрузки Росстата", msg)

    def _on_rosstat_finished(self):
        self._set_busy(False)

        if self._rosstat_worker is not None:
            self._rosstat_worker.deleteLater()
        if self._rosstat_thread is not None:
            self._rosstat_thread.deleteLater()

        self._rosstat_worker = None
        self._rosstat_thread = None

    # -------- CALC / EXPORT --------
    def on_calc(self):
        try:
            for w in (self.price_ai92, self.price_ai95, self.price_dt_summer, self.price_dt_winter):
                self._format_money_field(w, decimals=2, group=False)
            self._format_percent_field()

            vals = self._collect_required_decimals_for_calc()
            if vals is None:
                return

            qdate = self.date_state.date()
            base_month = qdate.month()

            inflation_percent = vals["infl"]
            inflation_factor = Decimal("1") + (inflation_percent - Decimal("100")) / Decimal("100")

            inp = CalcInput(
                base_month=base_month,
                inflation_year_factor=inflation_factor,
                price_ai92=vals["ai92"],
                price_ai95=vals["ai95"],
                price_dt_summer=vals["dt_s"],
                price_dt_winter=vals["dt_w"],
                manual_degrees=self.manual_degrees.isChecked(),
                n_start=int(self.n_start.value()),
                n_end=int(self.n_end.value()),
            )

            out = calc(inp)

            if not self.manual_degrees.isChecked():
                self.n_start.setValue(out.n_start)
                self.n_end.setValue(out.n_end)

            prices = [inp.price_ai92, inp.price_ai95, inp.price_dt_summer, inp.price_dt_winter]
            sums = [out.sum_ai92, out.sum_ai95, out.sum_dt_summer, out.sum_dt_winter]

            for r in range(4):
                self.table.setItem(r, 4, QTableWidgetItem(fmt_money(prices[r])))
                self.table.setItem(r, 5, QTableWidgetItem(fmt_decimal(out.ipc_period, 2)))
                self.table.setItem(r, 6, QTableWidgetItem(fmt_money(sums[r])))

            self.table.setItem(4, 6, QTableWidgetItem(fmt_money(out.total_sum)))

            self._last_calc_out = out
            self._last_calc_inp = inp

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

    def _supply_period_by_rule(self, base_month: int, state_year: int):
        if base_month < 6:
            return (7, state_year), (12, state_year)
        if base_month > 9:
            return (1, state_year + 1), (6, state_year + 1)
        raise ValueError("Для базового месяца июнь–сентябрь период поставки задайте вручную (пока не реализовано).")

    def on_export_docx(self):
        try:
            self._format_max_contract_field()
            max_price_dec = self._collect_required_decimals_for_export()
            if max_price_dec is None:
                return

            if self._last_calc_out is None or self._last_calc_inp is None:
                QMessageBox.information(self, "Экспорт", "Сначала нажмите «Рассчитать».")
                return

            out = self._last_calc_out
            inp = self._last_calc_inp

            qd_state = self.date_state.date()
            date_state_py = dt_date(qd_state.year(), qd_state.month(), qd_state.day())

            qd_doc = self.date_doc.date()
            doc_date_py = dt_date(qd_doc.year(), qd_doc.month(), qd_doc.day())

            (m_start, y_start), (m_end, y_end) = self._supply_period_by_rule(inp.base_month, date_state_py.year)
            inflation_year = y_start

            total_words = money_to_words(out.total_sum)
            max_words = money_to_words(max_price_dec)

            # "748 876,00"
            max_price_str = f"{max_price_dec:,.2f}".replace(",", " ").replace(".", ",")
            # "748 876" (целые рубли)
            max_contract_rub_str = f"{max_words.rub:,}".replace(",", " ")

            inflation_percent_str = self.inflation_percent.text().strip()
            inflation_factor_str = fmt_decimal(inp.inflation_year_factor, 3)

            # Собираем контекст как dict, потом фильтруем под реальные поля ExportData
            ctx = dict(
                date_state=date_state_py.strftime("%d.%m.%Y"),

                inflation_year_percent=inflation_percent_str,
                inflation_year=str(inflation_year),
                inflation_year_next1=str(inflation_year + 1),
                inflation_year_next2=str(inflation_year + 2),

                inflation_year_factor=inflation_factor_str,
                monthly_index=fmt_decimal(out.monthly_index, 4),

                n_start=out.n_start,
                n_end=out.n_end,

                deflator_start=fmt_decimal(out.deflator_start, 4),
                deflator_end=fmt_decimal(out.deflator_end, 4),

                ipc_period=fmt_decimal(out.ipc_period, 2),

                price_ai92=fmt_money(inp.price_ai92),
                price_ai95=fmt_money(inp.price_ai95),
                price_dt_summer=fmt_money(inp.price_dt_summer),
                price_dt_winter=fmt_money(inp.price_dt_winter),

                sum_ai92=fmt_money(out.sum_ai92),
                sum_ai95=fmt_money(out.sum_ai95),
                sum_dt_summer=fmt_money(out.sum_dt_summer),
                sum_dt_winter=fmt_money(out.sum_dt_winter),

                total_sum=fmt_money(out.total_sum),
                total_rub=str(total_words.rub),
                total_kop=f"{total_words.kop:02d}",
                total_rub_words=total_words.rub_words,
                total_kop_words=total_words.kop_words,
                total_rub_word=total_words.rub_word,
                total_kop_word=total_words.kop_word,

                # оставляем и полное значение, если оно где-то нужно
                max_contract_price=max_price_str,
                # НОВОЕ: целые рубли (для строки "Максимальное значение цены контракта: 748 876 (...) ...")
                max_contract_rub=max_contract_rub_str,

                max_contract_rub_words=max_words.rub_words,
                max_contract_rub_word=max_words.rub_word,
                max_contract_kop=f"{max_words.kop:02d}",
                max_contract_kop_word=max_words.kop_word,

                supply_start_month_name=MONTHS_RU_NOM[m_start],
                supply_start_year=str(y_start),
                supply_end_month_name=MONTHS_RU_NOM[m_end],
                supply_end_year=str(y_end),

                doc_date=doc_date_py.strftime("%d.%m.%Y"),
            )

            # Фильтруем под актуальные поля ExportData (чтобы не падать, если поле ещё не добавлено)
            allowed = set(getattr(ExportData, "__dataclass_fields__", {}).keys())
            filtered = {k: v for k, v in ctx.items() if k in allowed}

            data = ExportData(**filtered)

            default_name = f"Обоснование НМЦК от {doc_date_py.strftime('%d.%m.%Y')}.docx"
            path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить DOCX",
                str(Path.home() / default_name),
                "Word document (*.docx)"
            )
            if not path_str:
                return

            export_docx(data, Path(path_str))
            QMessageBox.information(self, "Экспорт", f"Файл сохранён:\n{path_str}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))