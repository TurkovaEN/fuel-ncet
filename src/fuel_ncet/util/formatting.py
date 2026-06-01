from decimal import Decimal


def parse_decimal_ru(text: str) -> Decimal:
    """
    '60,23' -> Decimal('60.23')
    '748 876,00' -> Decimal('748876.00')
    """
    t = text.strip().replace(" ", "").replace(",", ".")
    if not t:
        raise ValueError("Пустое значение")
    return Decimal(t)


def fmt_money(d: Decimal) -> str:
    """Decimal('60.2') -> '60,20'"""
    s = f"{d:.2f}"
    return s.replace(".", ",")


def fmt_decimal(d: Decimal, places: int) -> str:
    s = f"{d:.{places}f}"
    return s.replace(".", ",")