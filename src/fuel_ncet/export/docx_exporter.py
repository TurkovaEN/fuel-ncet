from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

from docxtpl import DocxTemplate

from fuel_ncet.util.formatting import fmt_money, fmt_decimal
from fuel_ncet.util.ru_money import money_to_words


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
    Чтобы работало и в PyCharm, и в .exe (PyInstaller).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[3]  # .../src/fuel_ncet/export -> корень проекта
    return base / rel


@dataclass
class ExportData:
    date_state: date
    inflation_year_percent: str          # '104,0'
    inflation_year_factor: str           # '1,040'
    monthly_index: str                   # '1,0033'
    n_start: int
    n_end: int
    deflator_start: str                  # '1,0099'
    deflator_end: str                    # '1,0264'
    ipc_period: str                      # '1,02'

    price_ai92: str
    price_ai95: str
    price_dt_summer: str
    price_dt_winter: str

    sum_ai92: str
    sum_ai95: str
    sum_dt_summer: str
    sum_dt_winter: str

    total_sum: str                       # '283,90'
    total_rub: str                       # '283'
    total_kop: str                       # '90'
    total_rub_words: str                 # 'двести ...'
    total_kop_words: str                 # 'девяносто'
    total_rub_word: str                  # 'рубля'
    total_kop_word: str                  # 'копеек'

    max_contract_price: str              # '748 876,00'
    max_contract_rub_words: str
    max_contract_rub_word: str
    max_contract_kop: str
    max_contract_kop_word: str

    supply_start_month_name: str
    supply_start_year: str
    supply_end_month_name: str
    supply_end_year: str

    inflation_year: str
    inflation_year_next1: str
    inflation_year_next2: str

    doc_date: str                        # системная дата '10.04.2026'


def export_docx(data: ExportData, out_path: Path) -> None:
    template_path = _resource_path("assets/template.docx")
    doc = DocxTemplate(str(template_path))

    context = data.__dict__
    doc.render(context)
    doc.save(str(out_path))