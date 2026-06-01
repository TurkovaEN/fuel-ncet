from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from num2words import num2words


@dataclass
class MoneyWords:
    rub: int
    kop: int
    rub_words: str
    kop_words: str
    rub_word: str
    kop_word: str


def _round2(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _morph(n: int, one: str, two_four: str, five_zero: str) -> str:
    """
    1 рубль, 2-4 рубля, 5-0 рублей + исключение 11-14.
    """
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return five_zero
    last = n_abs % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return two_four
    return five_zero


def money_to_words(amount: Decimal) -> MoneyWords:
    """
    amount: Decimal('283.90') -> 283 рубля 90 копеек (и прописью)
    """
    amount = _round2(amount)
    rub = int(amount)
    kop = int((amount - Decimal(rub)) * 100)

    rub_words = num2words(rub, lang="ru")
    kop_words = num2words(kop, lang="ru")

    rub_word = _morph(rub, "рубль", "рубля", "рублей")
    kop_word = _morph(kop, "копейка", "копейки", "копеек")

    return MoneyWords(
        rub=rub,
        kop=kop,
        rub_words=rub_words,
        kop_words=kop_words,
        rub_word=rub_word,
        kop_word=kop_word,
    )