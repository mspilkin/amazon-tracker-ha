"""Parser tests — pure function tests against saved HTML fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app import parsers
from app.scrapers.order_detail import parse_detail_html
from app.scrapers.orders_list import OrderSummary, _parse_cards, _window_start

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---- parsers primitives ---------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$12.34", (12.34, "USD")),
        ("$1,234.56", (1234.56, "USD")),
        ("£9.99", (9.99, "GBP")),
        ("€49.00", (49.00, "EUR")),
        ("Order total: $0.99", (0.99, "USD")),
        ("", (None, None)),
        ("free", (None, None)),
    ],
)
def test_parse_currency(raw, expected):
    assert parsers.parse_currency(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("January 12, 2026", date(2026, 1, 12)),
        ("Jan 12, 2026", date(2026, 1, 12)),
        ("12 January 2026", date(2026, 1, 12)),
        ("nonsense", None),
        ("", None),
    ],
)
def test_parse_order_date(raw, expected):
    assert parsers.parse_order_date(raw) == expected


def test_parse_eta_today_tomorrow():
    today = date(2026, 4, 17)
    assert parsers.parse_eta("Arriving Today", today=today) == today
    assert parsers.parse_eta("Tomorrow", today=today) == date(2026, 4, 18)


def test_parse_eta_with_weekday():
    today = date(2026, 1, 10)
    assert parsers.parse_eta("Arriving Tue, Jan 13", today=today) == date(2026, 1, 13)


def test_parse_eta_with_explicit_year():
    assert parsers.parse_eta("Arriving Jan 13, 2027") == date(2027, 1, 13)


def test_parse_eta_year_rollover():
    """If the parsed date would be >6 months in the past, it rolls to next year."""
    today = date(2026, 11, 1)
    assert parsers.parse_eta("Arriving Jan 5", today=today) == date(2027, 1, 5)


def test_extract_order_id():
    assert (
        parsers.extract_order_id("Order # 112-1234567-1234567")
        == "112-1234567-1234567"
    )
    assert parsers.extract_order_id("no id here") is None


def test_extract_asin():
    assert parsers.extract_asin("/gp/product/B08N5WRWNW/ref=foo") == "B08N5WRWNW"
    assert parsers.extract_asin("/dp/B07FZ8S74R") == "B07FZ8S74R"
    assert parsers.extract_asin(None) is None


def test_normalise_status_maps_common_phrases():
    assert parsers.normalise_status("Delivered January 2") == "delivered"
    assert parsers.normalise_status("Out for delivery") == "out_for_delivery"
    assert parsers.normalise_status("Arriving tomorrow") == "shipped"
    assert parsers.normalise_status("Order placed") == "placed"
    assert parsers.normalise_status("Cancelled") == "cancelled"
    assert parsers.normalise_status("") == "unknown"


# ---- orders_list ----------------------------------------------------------

def test_parse_cards_happy_path():
    html = read("order_list_sample.html")
    # Pin window start to early 2025 so the 2020 card is excluded.
    summaries, had_older = _parse_cards(html, window_start=date(2025, 1, 1))
    ids = [s.order_id for s in summaries]
    assert "112-1234567-1234567" in ids
    assert "113-7654321-7654321" in ids
    assert "114-0000000-0000000" not in ids
    assert had_older is True

    first = next(s for s in summaries if s.order_id == "112-1234567-1234567")
    assert first.order_date == date(2026, 1, 12)
    assert first.total_amount == 49.99
    assert first.currency == "USD"
    assert first.raw_status_text == "Arriving tomorrow"


def test_parse_cards_falls_back_when_data_components_missing():
    """Regression guard: Amazon has removed data-* attrs before; we fall back on class fragments."""
    html = read("order_list_legacy.html")
    summaries, _ = _parse_cards(html, window_start=date(2025, 1, 1))
    assert len(summaries) == 1
    assert summaries[0].order_id == "115-5555555-5555555"
    assert summaries[0].total_amount == 25.00
    assert summaries[0].raw_status_text == "Shipped"


def test_parse_cards_on_empty_page_returns_empty_list():
    html = "<!doctype html><html><body><div>No orders.</div></body></html>"
    summaries, had_older = _parse_cards(html, window_start=date(2025, 1, 1))
    assert summaries == []
    assert had_older is False


def test_window_start_uses_months():
    today = date(2026, 4, 17)
    ws = _window_start(24, today=today)
    # 24 * 30 = 720 days back
    assert (today - ws).days == 720


# ---- order_detail ---------------------------------------------------------

def test_parse_detail_full():
    summary = OrderSummary(
        order_id="112-1234567-1234567",
        order_date=date(2026, 1, 10),
        total_amount=38.48,
        currency="USD",
        raw_status_text="Arriving tomorrow",
    )
    order = parse_detail_html(read("order_detail_sample.html"), summary=summary)
    assert order.order_id == summary.order_id
    assert order.carrier == "UPS"
    assert order.tracking_number == "1Z999AA10123456784"
    assert order.payment_method == "Visa ending in 1234"
    assert order.delivery_photo_url == "https://m.media-amazon.com/images/I/photo.jpg"
    assert order.status == "shipped"

    titles = [item.title for item in order.items]
    assert "Echo Dot (4th Gen)" in titles
    assert "USB-C Cable 6ft" in titles
    echo = next(i for i in order.items if i.title == "Echo Dot (4th Gen)")
    assert echo.asin == "B08N5WRWNW"
    assert echo.unit_price == 29.99
    assert echo.thumbnail_url and "echo_thumb" in echo.thumbnail_url


def test_parse_detail_missing_optional_fields():
    """Detail page with no delivery photo, no carrier, no tracking — must not crash."""
    html = """
    <html><body>
      <div class="items">
        <div data-component="orderItem" class="item-box">
          <a class="a-link-normal" href="/dp/B00000TEST">Test Product</a>
          <div class="a-color-price">$5.00</div>
        </div>
      </div>
    </body></html>
    """
    summary = OrderSummary(
        order_id="200-0000000-0000000",
        order_date=date(2026, 2, 1),
        total_amount=5.00,
        currency="USD",
        raw_status_text="Delivered",
    )
    order = parse_detail_html(html, summary=summary)
    assert order.items[0].title == "Test Product"
    assert order.carrier is None
    assert order.tracking_number is None
    assert order.delivery_photo_url is None
    assert order.status == "delivered"
    assert order.delivered_at is not None
