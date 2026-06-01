from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


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
    monthly_index: Decimal
    n_start: int
    n_end: int
    deflator_start: Decimal
    deflator_end: Decimal
    ipc_period: Decimal
    sum_ai92: Decimal
    sum_ai95: Decimal
    sum_dt_summer: Decimal
    sum_dt_winter: Decimal
    total_sum: Decimal


def _round(d: Decimal, places: int) -> Decimal:
    q = Decimal("1").scaleb(-places)
    return d.quantize(q, rounding=ROUND_HALF_UP)


def compute_degrees_by_rule(base_month: int) -> tuple[int, int]:
    # base_month < 6 -> до июля/декабря
    # base_month > 9 -> до января/июня следующего года
    if base_month < 6:
        return 7 - base_month, 12 - base_month
    if base_month > 9:
        return (12 - base_month) + 1, (12 - base_month) + 6

    raise ValueError(
        "Для базового месяца июнь–сентябрь степени нужно задать вручную "
        "(включите 'Править степени вручную')."
    )


def calc(inp: CalcInput) -> CalcOutput:
    # Ежемесячный индекс: m = factor^(1/12)
    # ВАЖНО: округляем m до 4 знаков ДО возведения в степень (как в вашем прежнем варианте)
    factor_f = float(inp.inflation_year_factor)
    m = Decimal(str(factor_f ** (1.0 / 12.0)))
    m = _round(m, 4)

    if inp.manual_degrees:
        n_start, n_end = inp.n_start, inp.n_end
    else:
        n_start, n_end = compute_degrees_by_rule(inp.base_month)

    defl_start = Decimal(str(float(m) ** n_start))
    defl_end = Decimal(str(float(m) ** n_end))
    defl_start = _round(defl_start, 4)
    defl_end = _round(defl_end, 4)

    ipc = (defl_start + defl_end) / Decimal("2")
    ipc = _round(ipc, 2)

    s1 = _round(inp.price_ai92 * ipc, 2)
    s2 = _round(inp.price_ai95 * ipc, 2)
    s3 = _round(inp.price_dt_summer * ipc, 2)
    s4 = _round(inp.price_dt_winter * ipc, 2)
    total = _round(s1 + s2 + s3 + s4, 2)

    return CalcOutput(
        monthly_index=m,
        n_start=n_start,
        n_end=n_end,
        deflator_start=defl_start,
        deflator_end=defl_end,
        ipc_period=ipc,
        sum_ai92=s1,
        sum_ai95=s2,
        sum_dt_summer=s3,
        sum_dt_winter=s4,
        total_sum=total,
    )