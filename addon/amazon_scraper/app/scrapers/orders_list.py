"""Order-history list scraper.

Walks /gp/your-account/order-history?timeFilter=year-YYYY pages, collecting
per-order summaries. `months` controls how far back we iterate — e.g. months=24
scrapes the current and previous calendar year, then stops when a page yields
no cards within the window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from .. import parsers
from . import selectors as sel

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..browser import BrowserManager

_LOGGER = logging.getLogger(__name__)


@dataclass
class OrderSummary:
    order_id: str
    order_date: date
    total_amount: float
    currency: str
    raw_status_text: str | None


def _year_filters(months: int, today: date | None = None) -> list[str]:
    """Return year filter tokens to iterate, newest first."""
    today = today or datetime.now(timezone.utc).date()
    years_back = max(0, (months + 11) // 12)  # round up
    tokens = [f"year-{today.year - i}" for i in range(years_back + 1)]
    return tokens


async def _fetch_page_html(
    page: "Page", browser: "BrowserManager", *, base_url: str, year_filter: str, start_index: int
) -> str:
    params = {"timeFilter": year_filter}
    if start_index:
        params["startIndex"] = str(start_index)
    url = f"{base_url}/gp/your-account/order-history?{urlencode(params)}"
    await browser.goto(page, url)
    return await page.content()


def _parse_cards(html: str, *, window_start: date) -> tuple[list[OrderSummary], bool]:
    """Parse one order-history page.

    Returns (summaries, had_older_than_window). The second value lets the caller
    stop paginating once we've walked past the configured history window.
    """
    soup = parsers.soup_of(html)
    cards = parsers.all_matches(soup, sel.ORDER_CARD)
    summaries: list[OrderSummary] = []
    had_older = False

    for card in cards:
        id_el = parsers.first_match(card, sel.ORDER_ID_IN_CARD)
        order_id = parsers.extract_order_id(id_el.get_text() if id_el else "")
        if not order_id:
            # Some cards embed the ID elsewhere — try the whole card text.
            order_id = parsers.extract_order_id(card.get_text(" "))
        if not order_id:
            continue

        date_el = parsers.first_match(card, sel.ORDER_DATE_IN_CARD)
        order_date = parsers.parse_order_date(
            date_el.get_text() if date_el else ""
        )
        if order_date is None:
            continue

        if order_date < window_start:
            had_older = True
            continue

        total_el = parsers.first_match(card, sel.ORDER_TOTAL_IN_CARD)
        total_text = total_el.get_text() if total_el else ""
        amount, currency = parsers.parse_currency(total_text)
        if amount is None:
            continue

        status_el = parsers.first_match(card, sel.ORDER_STATUS_IN_CARD)
        raw_status = parsers.clean(status_el.get_text()) if status_el else None

        summaries.append(
            OrderSummary(
                order_id=order_id,
                order_date=order_date,
                total_amount=amount,
                currency=currency or "USD",
                raw_status_text=raw_status,
            )
        )

    return summaries, had_older


def _window_start(months: int, today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    # Approximate: months * 30 days is fine for a cutoff.
    return date.fromordinal(today.toordinal() - months * 30)


async def scrape(
    page: "Page",
    browser: "BrowserManager",
    *,
    base_url: str,
    months: int,
) -> list[OrderSummary]:
    window_start = _window_start(months)
    summaries: list[OrderSummary] = []
    seen_ids: set[str] = set()

    for year_filter in _year_filters(months):
        start_index = 0
        while True:
            html = await _fetch_page_html(
                page,
                browser,
                base_url=base_url,
                year_filter=year_filter,
                start_index=start_index,
            )
            page_summaries, had_older = _parse_cards(html, window_start=window_start)
            new = [s for s in page_summaries if s.order_id not in seen_ids]
            for s in new:
                seen_ids.add(s.order_id)
            summaries.extend(new)

            # Pagination: Amazon shows 10 orders per page. Stop when we see no
            # new cards on the page (either exhausted or paginated off).
            if not new:
                break
            # Stop the whole walk once we've passed the window cutoff.
            if had_older:
                break
            start_index += 10
            # Hard safety cap per year — a typical account won't have 500+/year.
            if start_index > 500:
                break
        if had_older:
            break

    _LOGGER.info("orders_list: %d summaries within %d-month window", len(summaries), months)
    return summaries
