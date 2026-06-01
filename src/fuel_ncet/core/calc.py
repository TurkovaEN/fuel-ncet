from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext


# повышаем точность, чтобы не было расхождений на 4-м знаке
getcontext().prec = 50


@dataclass
class CalcInput:
    base_month: int                 # месяц даты состояния (1..12)
    inflation_year_factor: Decimal  # например 1.040 для 104,0%
    price_ai92: Decimal
    price_ai95: Decimal
    price_dt_summer: Decimal
    price_dt_winter: Decimal
    manual_degrees: bool = False
    n_start: int = 0
    n_end: int = 0


@dataclass
class CalcOutput:
    monthly_index: Decimal          # m (округлённый для отображения)
    n_start: int
    n_end: int
    deflator_start: Decimal         # d_start
    deflator_end: Decimal           # d_end
    ipc_period: Decimal             # ИПЦ на период поставки (среднее)
    sum_ai92: Decimal
    sum_ai95: Decimal
    sum_dt_summer: Decimal
    sum_dt_winter: Decimal
    total_sum: Decimal


def _round(d: Decimal, places: int) -> Decimal:
    q = Decimal("1").scaleb(-places)
    return d.quantize(q, rounding=ROUND_HALF_UP)


def compute_degrees_by_rule(base_month: int) -> tuple[int, int]:
    """
    Ваша логика:
    - если base_month < 6  -> степени до июля и до декабря (текущий год)
    - если base_month > 9  -> степени до января и до июня (следующий год)
    """
    if base_month < 6:
        return 7 - base_month, 12 - base_month
    if base_month > 9:
        return (12 - base_month) + 1, (12 - base_month) + 6

    raise ValueError(
        "Для базового месяца июнь–сентябрь степени нужно задать вручную "
        "(включите 'Править степени вручную')."
    )


def calc(inp: CalcInput) -> CalcOutput:
    if inp.inflation_year_factor <= 0:
        raise ValueError("Индекс прогнозной инфляции должен быть > 0")

    # Точный ежемесячный индекс: m = exp( ln(factor) / 12 )
    m_raw = (inp.inflation_year_factor.ln() / Decimal(12)).exp()

    # monthly_index в выводе — округляем до 4 знаков, как в документе
    m_display = _round(m_raw, 4)

    if inp.manual_degrees:
        n_start, n_end = inp.n_start, inp.n_end
    else:
        n_start, n_end = compute_degrees_by_rule(inp.base_month)

    # дефляторы считаем от НЕокруглённого m_raw
    d_start = _round(m_raw ** int(n_start), 4)
    d_end = _round(m_raw ** int(n_end), 4)

    ipc = _round((d_start + d_end) / Decimal("2"), 2)

    s1 = _round(inp.price_ai92 * ipc, 2)
    s2 = _round(inp.price_ai95 * ipc, 2)
    s3 = _round(inp.price_dt_summer * ipc, 2)
    s4 = _round(inp.price_dt_winter * ipc, 2)
    total = _round(s1 + s2 + s3 + s4, 2)

    return CalcOutput(
        monthly_index=m_display,
        n_start=n_start,
        n_end=n_end,
        deflator_start=d_start,
        deflator_end=d_end,
        ipc_period=ipc,
        sum_ai92=s1,
        sum_ai95=s2,
        sum_dt_summer=s3,
        sum_dt_winter=s4,
        total_sum=total,
    )