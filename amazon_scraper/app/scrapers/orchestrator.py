"""Orchestrator: composes order-list, order-detail, and returns scrapers into one run.

Task-3 populates the actual scraper modules. This file wires them together and
owns dump-on-failure, anti-bot pacing, and result assembly.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from ..browser import BrowserManager, LoginRequiredError
from ..config import Settings
from ..models import Order, ReturnRecord, ScrapeResult
from . import orders_list, order_detail, returns as returns_scraper
from .selectors import SELECTOR_VERSION

_LOGGER = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, settings: Settings, browser: BrowserManager) -> None:
        self.settings = settings
        self.browser = browser

    # ---- public entry points --------------------------------------------

    async def run_full(self, *, history_months: int | None = None) -> ScrapeResult:
        months = history_months or self.settings.history_months
        return await self._run(months=months, active_order_ids=[], full=True)

    async def run_incremental(
        self, *, active_order_ids: Iterable[str], since: date | None
    ) -> ScrapeResult:
        return await self._run(
            months=1,  # page 1 of current year is always enough for "new since last run"
            active_order_ids=list(active_order_ids),
            full=False,
        )

    # ---- internal --------------------------------------------------------

    async def _run(
        self, *, months: int, active_order_ids: list[str], full: bool
    ) -> ScrapeResult:
        orders: list[Order] = []
        returns: list[ReturnRecord] = []
        orders_seen = 0
        outcome: str = "success"
        error_message: str | None = None

        try:
            async with self.browser.scrape_page() as page:
                # 1) List pass: walk order-history year filters.
                summaries = await orders_list.scrape(
                    page,
                    self.browser,
                    base_url=self.settings.base_url,
                    months=months,
                )
                orders_seen = len(summaries)

                # Build the set of orders whose details we'll fetch:
                # every summary for a full run; only changed/active for incremental.
                target_ids = {s.order_id for s in summaries}
                if not full and active_order_ids:
                    target_ids |= set(active_order_ids)

                # 2) Detail pass with jittered pacing.
                for summary in summaries:
                    if summary.order_id not in target_ids:
                        continue
                    await self._pace()
                    order = await order_detail.scrape(
                        page,
                        self.browser,
                        base_url=self.settings.base_url,
                        summary=summary,
                    )
                    if order is not None:
                        orders.append(order)

                # 3) Returns pass.
                await self._pace()
                returns = await returns_scraper.scrape(
                    page, self.browser, base_url=self.settings.base_url
                )

                # 4) Sanity check: list had cards previously but now returns 0
                # → selectors likely broke. Mark partial.
                if orders_seen == 0 and full:
                    outcome = "partial"
                    await self._dump_debug_html(page, reason="empty_order_list")

        except LoginRequiredError:
            raise
        except Exception as err:  # pragma: no cover - surfaced to caller
            _LOGGER.exception("scrape failed")
            outcome = "error"
            error_message = f"{type(err).__name__}: {err}"

        return ScrapeResult(
            outcome=outcome,  # type: ignore[arg-type]
            orders_seen=orders_seen,
            orders_changed=len(orders),
            orders=orders,
            returns=returns,
            error_message=error_message,
            selector_version=SELECTOR_VERSION,
        )

    async def _pace(self) -> None:
        await asyncio.sleep(random.uniform(1.2, 3.5))

    async def _dump_debug_html(self, page, *, reason: str) -> None:
        try:
            Path(self.settings.debug_dump_path).mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = Path(self.settings.debug_dump_path) / f"{ts}_{reason}.html"
            html = await page.content()
            path.write_text(html, encoding="utf-8")
            _LOGGER.warning("dumped debug HTML to %s", path)
        except Exception:  # pragma: no cover
            _LOGGER.exception("failed to dump debug HTML")
