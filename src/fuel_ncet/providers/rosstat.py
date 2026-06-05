from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, List, Tuple
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
    ssl_insecure_used: bool


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


def _parse_date_from_title(text: str) -> Optional[date]:
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
        raise ValueError("Не удалось найти значение Барнаула в строке: %s" % line)
    return float(nums[1].replace(",", "."))


def _looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _find_altai_link(doc_soup: BeautifulSoup) -> Optional[str]:
    hrefs = []
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


def _get(session: requests.Session, url: str, timeout: int = 40, verify: bool = True) -> requests.Response:
    r = session.get(url, timeout=timeout, allow_redirects=True, verify=verify)
    r.raise_for_status()
    return r


def _find_next_page_href(soup: BeautifulSoup) -> Optional[str]:
    for a in soup.find_all("a", href=True):
        txt = " ".join((a.get_text() or "").split())
        if txt == "Далее":
            return a["href"]
    for a in soup.find_all("a", href=True):
        rel = a.get("rel") or []
        if isinstance(rel, str):
            rel = [rel]
        rel = [str(x).lower() for x in rel]
        if "next" in rel:
            return a["href"]
    for a in soup.find_all("a", href=True):
        txt = " ".join((a.get_text() or "").split())
        if txt in ("»", "›", ">"):
            return a["href"]
    return None


def fetch_latest_prices(as_of: Optional[date] = None, cache_dir: Optional[Path] = None) -> RosstatPrices:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FuelNCET/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    verify = True
    ssl_insecure_used = False

    def safe_get(url: str) -> requests.Response:
        nonlocal verify, ssl_insecure_used
        try:
            return _get(session, url, verify=verify)
        except SSLError:
            verify = False
            ssl_insecure_used = True
            return _get(session, url, verify=verify)

    news_url = urljoin(BASE_URL, "news_stat")
    page_url = news_url

    candidates: List[Tuple[date, str]] = []
    visited = set()
    max_pages = 200

    for _ in range(max_pages):
        if page_url in visited:
            break
        visited.add(page_url)

        html = safe_get(page_url).text
        soup = BeautifulSoup(html, "lxml")

        page_candidates: List[Tuple[date, str]] = []
        for a in soup.find_all("a", href=True):
            text = (a.get_text() or "").strip()
            if "Потребительские цены на" not in text:
                continue
            d = _parse_date_from_title(text)
            if not d:
                continue
            if as_of is not None and d > as_of:
                continue
            page_candidates.append((d, a["href"]))

        if as_of is None:
            candidates = page_candidates
            break

        if page_candidates:
            candidates = page_candidates
            break

        next_href = _find_next_page_href(soup)
        if not next_href:
            break
        page_url = urljoin(BASE_URL, next_href)

    if not candidates:
        if as_of is not None:
            raise ValueError("Не найдены публикации Росстата не позже %s." % as_of.strftime("%d.%m.%Y"))
        raise ValueError("Не найдены публикации Росстата.")

    candidates.sort(key=lambda x: x[0], reverse=True)
    date_state, href = candidates[0]

    doc_url = urljoin(BASE_URL, href)
    doc_html = safe_get(doc_url).text
    doc_soup = BeautifulSoup(doc_html, "lxml")

    altai_href = _find_altai_link(doc_soup)
    if not altai_href:
        raise ValueError("На странице документа не найдена ссылка 'Алтайский край'.")

    pdf_url = urljoin(BASE_URL, altai_href)

    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / ("rosstat_%s.pdf" % date_state.isoformat())

    if cache_path is not None and cache_path.exists():
        pdf_bytes = cache_path.read_bytes()
    else:
        resp = safe_get(pdf_url)
        pdf_bytes = resp.content
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if (not _looks_like_pdf(pdf_bytes)) and ("pdf" not in content_type):
            snippet = pdf_bytes[:400].decode("utf-8", errors="replace")
            raise ValueError("Ссылка вернула не PDF. Первые символы:\n%s" % snippet)
        if cache_path is not None:
            cache_path.write_bytes(pdf_bytes)

    ai92 = None
    ai95 = None
    diesel = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
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
        raise ValueError("Не удалось извлечь значения из PDF.")

    return RosstatPrices(
        date_state=date_state,
        ai92_barnaul=ai92,
        ai95_barnaul=ai95,
        diesel_barnaul=diesel,
        source_url=doc_url,
        pdf_url=pdf_url,
        ssl_insecure_used=ssl_insecure_used,
    )