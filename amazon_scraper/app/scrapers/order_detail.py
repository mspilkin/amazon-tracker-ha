"""Order-detail scraper."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from .. import parsers
from ..models import Item, Order
from . import selectors as sel
from .orders_list import OrderSummary

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..browser import BrowserManager

_LOGGER = logging.getLogger(__name__)


async def scrape(
    page: "Page",
    browser: "BrowserManager",
    *,
    base_url: str,
    summary: OrderSummary,
) -> Order | None:
    url = f"{base_url}/gp/your-account/order-details?{urlencode({'orderID': summary.order_id})}"
    try:
        await browser.goto(page, url)
    except Exception:
        _LOGGER.exception("order-detail navigation failed for %s", summary.order_id)
        return None

    html = await page.content()
    return parse_detail_html(html, summary=summary)


def parse_detail_html(html: str, *, summary: OrderSummary) -> Order:
    """Pure function: DOM → Order. Tested directly against fixtures."""
    soup = parsers.soup_of(html)

    items: list[Item] = []
    for row in parsers.all_matches(soup, sel.DETAIL_ITEM_ROW):
        title_el = parsers.first_match(row, sel.DETAIL_ITEM_TITLE)
        if title_el is None:
            continue
        title = parsers.clean(title_el.get_text())
        if not title:
            continue
        asin = parsers.extract_asin(title_el.get("href"))

        thumb_el = parsers.first_match(row, sel.DETAIL_ITEM_THUMBNAIL)
        thumbnail = thumb_el.get("src") if thumb_el else None

        price_el = parsers.first_match(row, sel.DETAIL_ITEM_PRICE)
        unit_price, _ = parsers.parse_currency(price_el.get_text() if price_el else "")

        items.append(
            Item(
                asin=asin,
                title=title,
                thumbnail_url=thumbnail,
                unit_price=unit_price,
            )
        )

    carrier_el = parsers.first_match(soup, sel.DETAIL_CARRIER)
    carrier = parsers.clean(carrier_el.get_text()) if carrier_el else None

    tracking_el = parsers.first_match(soup, sel.DETAIL_TRACKING_NUMBER)
    tracking_number = parsers.clean(tracking_el.get_text()) if tracking_el else None

    eta_el = parsers.first_match(soup, sel.DETAIL_ETA)
    eta_text = parsers.clean(eta_el.get_text()) if eta_el else ""
    eta_date = parsers.parse_eta(eta_text) if eta_text else None

    photo_el = parsers.first_match(soup, sel.DETAIL_DELIVERY_PHOTO)
    delivery_photo_url = photo_el.get("src") if photo_el else None

    payment_el = parsers.first_match(soup, sel.DETAIL_PAYMENT_METHOD)
    payment_method = parsers.clean(payment_el.get_text()) if payment_el else None

    status = parsers.normalise_status(summary.raw_status_text or eta_text)
    delivered_at = (
        datetime.now(timezone.utc)
        if status == "delivered"
        else None
    )

    return Order(
        order_id=summary.order_id,
        order_date=summary.order_date,
        total_amount=summary.total_amount,
        currency=summary.currency,
        payment_method=payment_method,
        status=status,  # type: ignore[arg-type]
        raw_status_text=summary.raw_status_text,
        carrier=carrier,
        tracking_number=tracking_number,
        eta_date=eta_date,
        delivered_at=delivered_at,
        delivery_photo_url=delivery_photo_url,
        items=items,
    )
