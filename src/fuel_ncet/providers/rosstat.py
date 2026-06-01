from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import io
import re
from urllib.parse import urljoin

import pdfplumber
import requests
from requests.exceptions import SSLError
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_URL = "https://22.rosstat.gov.ru/"


@dataclass
class RosstatPrices:
    date_state: date
    ai92_barnaul: float
    ai95_barnaul: float
    diesel_barnaul: float
    source_url: str
    pdf_url: str
    ssl_insecure_used: bool  # True если пришлось отключить проверку сертификата


_MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def _parse_date_from_title(text: str) -> date | None:
    t = " ".join(text.split())
    m = re.search(r"на\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s+года", t, re.IGNORECASE)
    if not m:
        return None
    day = int(m.group(1))
    mon_name = m.group(2).lower()
    year = int(m.group(3))
    mon = _MONTHS_RU.get(mon_name)
    if not mon:
        return None
    return date(year, mon, day)


def _extract_barnaul_value_from_line(line: str) -> float:
    nums = re.findall(r"\d+,\d+", line)
    if len(nums) < 2:
        raise ValueError(f"Не удалось найти значение Барнаула в строке: {line}")
    return float(nums[1].replace(",", "."))


def _looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _find_altai_link(doc_soup: BeautifulSoup) -> str | None:
    hrefs: list[str] = []
    for a in doc_soup.find_all("a", href=True):
        t = (a.get_text() or "").strip()
        if t == "Алтайский край":
            hrefs.append(a["href"])

    if not hrefs:
        return None

    for h in hrefs:
        hl = h.lower()
        if ".pdf" in hl or "download" in hl or "/system/files" in hl:
            return h

    return hrefs[0]


def _get(session: requests.Session, url: str, timeout: int = 30, verify: bool = True) -> requests.Response:
    r = session.get(url, timeout=timeout, allow_redirects=True, verify=verify)
    r.raise_for_status()
    return r


def fetch_latest_prices() -> RosstatPrices:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FuelNCET/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # Сначала пробуем безопасно verify=True, если не получится — повторяем verify=False
    verify = True
    ssl_insecure_used = False

    def safe_get(url: str) -> requests.Response:
        nonlocal verify, ssl_insecure_used
        try:
            return _get(session, url, verify=verify)
        except SSLError:
            # fallback: отключаем проверку сертификата
            verify = False
            ssl_insecure_used = True
            return _get(session, url, verify=verify)

    # 1) страница публикаций
    news_url = urljoin(BASE_URL, "news_stat")
    html = safe_get(news_url).text
    soup = BeautifulSoup(html, "lxml")

    # 2) ссылки "Потребительские цены на ..."
    candidates: list[tuple[date, str]] = []
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        if "Потребительские цены на" not in text:
            continue
        d = _parse_date_from_title(text)
        if not d:
            continue
        candidates.append((d, a["href"]))

    if not candidates:
        raise ValueError("Не найдены публикации 'Потребительские цены на ...' на странице /news_stat.")

    candidates.sort(key=lambda x: x[0], reverse=True)
    date_state, href = candidates[0]
    doc_url = urljoin(BASE_URL, href)

    # 3) страница документа
    doc_html = safe_get(doc_url).text
    doc_soup = BeautifulSoup(doc_html, "lxml")

    altai_href = _find_altai_link(doc_soup)
    if not altai_href:
        raise ValueError("На странице документа не найдена ссылка 'Алтайский край'.")

    pdf_url = urljoin(BASE_URL, altai_href)

    # 4) скачиваем PDF (проверяем, что это реально PDF)
    resp = safe_get(pdf_url)
    content = resp.content
    content_type = (resp.headers.get("Content-Type") or "").lower()

    if (not _looks_like_pdf(content)) and ("pdf" not in content_type):
        snippet = content[:400]
        snippet_text = snippet.decode("utf-8", errors="replace")
        raise ValueError(
            "Ссылка 'Алтайский край' вернула не PDF.\n"
            f"URL: {pdf_url}\n"
            f"Content-Type: {content_type}\n"
            "Первые символы ответа:\n"
            f"{snippet_text}"
        )

    # 5) парсим PDF
    ai92 = ai95 = diesel = None

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = " ".join(line.split())

                if "Дизельное топливо, л" in line:
                    diesel = _extract_barnaul_value_from_line(line)
                elif "Бензин автомобильный марки АИ-92, л" in line:
                    ai92 = _extract_barnaul_value_from_line(line)
                elif "Бензин автомобильный марки АИ-95, л" in line:
                    ai95 = _extract_barnaul_value_from_line(line)

            if ai92 is not None and ai95 is not None and diesel is not None:
                break

    if ai92 is None or ai95 is None or diesel is None:
        raise ValueError(
            "Не удалось извлечь все значения из PDF. "
            "Возможно изменился формат PDF или строки перенеслись."
        )

    return RosstatPrices(
        date_state=date_state,
        ai92_barnaul=ai92,
        ai95_barnaul=ai95,
        diesel_barnaul=diesel,
        source_url=doc_url,
        pdf_url=pdf_url,
        ssl_insecure_used=ssl_insecure_used,
    )