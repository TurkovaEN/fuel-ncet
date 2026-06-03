from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from docxtpl import DocxTemplate


MONTHS_RU_NOM = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


def _resource_path(rel: str) -> Path:
    """
    Чтобы работало и в PyCharm, и в .exe (PyInstaller onefile).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[3]  # корень проекта
    return base / rel


@dataclass
class ExportData:
    # даты
    date_state: str
    doc_date: str

    # инфляция
    inflation_year_percent: str
    inflation_year_factor: str
    inflation_year: str
    inflation_year_next1: str
    inflation_year_next2: str

    monthly_index: str
    n_start: int
    n_end: int
    deflator_start: str
    deflator_end: str
    ipc_period: str

    # цены и суммы
    price_ai92: str
    price_ai95: str
    price_dt_summer: str
    price_dt_winter: str

    sum_ai92: str
    sum_ai95: str
    sum_dt_summer: str
    sum_dt_winter: str

    total_sum: str  # для таблицы "Итого" (с копейками)

    # прописью для "Начальная сумма..." (целые рубли + копейки)
    total_rub: str
    total_kop: str
    total_rub_words: str
    total_kop_words: str
    total_rub_word: str
    total_kop_word: str

    # максимальная цена контракта (целые рубли + копейки + пропись)
    max_contract_price: str  # можно оставить для других мест шаблона
    max_contract_rub: str    # ВАЖНО: целые рубли для строки "Максимальное значение..."
    max_contract_rub_words: str
    max_contract_rub_word: str
    max_contract_kop: str
    max_contract_kop_word: str

    # период поставки (для текста)
    supply_start_month_name: str
    supply_start_year: str
    supply_end_month_name: str
    supply_end_year: str


def export_docx(data: ExportData, out_path: Path) -> None:
    template_path = _resource_path("assets/template.docx")
    doc = DocxTemplate(str(template_path))
    doc.render(data.__dict__)
    doc.save(str(out_path))