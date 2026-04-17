"""Pure-function parsing helpers: DOM → model fields.

These are kept separate from the Playwright navigation code so they're easy to
test against saved HTML fixtures.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Iterable

from bs4 import BeautifulSoup, Tag

_LOGGER = logging.getLogger(__name__)

ORDER_ID_RE = re.compile(r"\b(D?\d{3}-\d{7}-\d{7})\b")
ASIN_RE = re.compile(r"/(?:gp/product|dp)/([A-Z0-9]{10})")
CURRENCY_RE = re.compile(
    r"(?P<sym>[$£€¥₹]|USD|GBP|EUR|JPY|CAD|AUD)\s?(?P<amt>[0-9][0-9,]*\.?[0-9]{0,2})"
)
# Amazon's ETA strings — keep short so we don't overfit to one locale.
ETA_DATE_RE = re.compile(
    r"\b("
    r"Today|Tomorrow|"
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:,?\s+\d{4})?"
    r")\b",
    re.IGNORECASE,
)

_CURRENCY_SYMBOL_TO_CODE = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "¥": "JPY",
    "₹": "INR",
}


# ---- selector fallback helper --------------------------------------------

def first_match(root: Tag, selectors: Iterable[str]) -> Tag | None:
    """Return the first element that matches any selector in order."""
    for sel in selectors:
        el = root.select_one(sel)
        if el is not None:
            return el
    return None


def all_matches(root: Tag, selectors: Iterable[str]) -> list[Tag]:
    """Return all elements from the first selector that yields a non-empty set."""
    for sel in selectors:
        found = root.select(sel)
        if found:
            return found
    return []


# ---- small primitives -----------------------------------------------------

def clean(text: str | None) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_order_id(text: str) -> str | None:
    match = ORDER_ID_RE.search(text or "")
    return match.group(1) if match else None


def extract_asin(href: str | None) -> str | None:
    if not href:
        return None
    match = ASIN_RE.search(href)
    return match.group(1) if match else None


def parse_currency(text: str) -> tuple[float | None, str | None]:
    """Return (amount, currency_code). Supports $, £, €, ¥, ₹ and 3-letter codes."""
    if not text:
        return None, None
    match = CURRENCY_RE.search(text)
    if not match:
        return None, None
    amount = float(match.group("amt").replace(",", ""))
    sym = match.group("sym")
    code = _CURRENCY_SYMBOL_TO_CODE.get(sym, sym.upper() if len(sym) == 3 else "USD")
    return amount, code


def parse_order_date(text: str) -> date | None:
    """Parse Amazon's order-list date format. Locale-resilient: tries a few layouts."""
    text = clean(text)
    if not text:
        return None
    # Common formats seen on amazon.com: "January 12, 2026", "Jan 12, 2026".
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_eta(text: str, *, today: date | None = None) -> date | None:
    """Parse Amazon's ETA pill. Returns None if unparseable.

    Handles: "Today", "Tomorrow", "Arriving Mon, Jan 12", "Arriving Jan 12, 2026".
    Year is inferred from `today` when absent.
    """
    if not text:
        return None
    today = today or date.today()
    match = ETA_DATE_RE.search(text)
    if not match:
        return None
    snippet = match.group(1).lower().strip()
    if snippet == "today":
        return today
    if snippet == "tomorrow":
        return today.fromordinal(today.toordinal() + 1)

    # Strip leading weekday + comma if present.
    snippet = re.sub(
        r"^(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+", "", snippet, flags=re.IGNORECASE
    )
    # Normalise "jan." → "jan"
    snippet = snippet.replace(".", "")

    for fmt in ("%b %d, %Y", "%b %d %Y", "%b %d"):
        try:
            parsed = datetime.strptime(snippet, fmt).date()
            if "%Y" not in fmt:
                parsed = parsed.replace(year=today.year)
                # If the inferred date is >6 months in the past, roll to next year.
                if (today - parsed).days > 180:
                    parsed = parsed.replace(year=today.year + 1)
            return parsed
        except ValueError:
            continue
    return None


def normalise_status(raw: str | None) -> str:
    """Map Amazon status strings to our canonical enum."""
    if not raw:
        return "unknown"
    text = raw.lower()
    if "delivered" in text:
        return "delivered"
    if "out for delivery" in text:
        return "out_for_delivery"
    if "shipped" in text or "on the way" in text or "arriving" in text:
        return "shipped"
    if "preparing" in text or "ordered" in text:
        return "preparing"
    if "placed" in text:
        return "placed"
    if "cancel" in text:
        return "cancelled"
    if "return" in text:
        return "returned"
    return "unknown"


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
