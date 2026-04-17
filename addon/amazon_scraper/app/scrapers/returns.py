"""Returns/refunds scraper. Phase-3 implements parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import ReturnRecord

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..browser import BrowserManager


async def scrape(
    page: "Page",
    browser: "BrowserManager",
    *,
    base_url: str,
) -> list[ReturnRecord]:
    # TODO(phase-3): GET /gp/your-account/ya-return-items, parse with selectors.RETURN_*.
    return []
