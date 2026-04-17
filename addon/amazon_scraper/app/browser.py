"""Playwright browser lifecycle + storage_state persistence.

One BrowserManager instance per process. Browser is launched lazily on first
use and kept warm across calls; a background task evicts it after `IDLE_TIMEOUT`
of inactivity to free memory.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .config import Settings

_LOGGER = logging.getLogger(__name__)

IDLE_TIMEOUT_SECONDS = 300

# Patched into every context so `navigator.webdriver === false` — cheap guard
# against the most common trivial bot checks.
_WEBDRIVER_SHIM = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""

SIGNIN_PATH_MARKERS = ("/ap/signin", "/ap/cvf", "/ap/mfa")


class LoginRequiredError(RuntimeError):
    """Raised when a request is redirected to Amazon sign-in."""


class BrowserManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._last_used = datetime.now(timezone.utc)
        self._idle_task: asyncio.Task[None] | None = None
        self._login_context: BrowserContext | None = None
        self._login_page: Page | None = None
        self.last_scrape_at: datetime | None = None

    # ---- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        if self._pw is not None:
            return
        self._pw = await async_playwright().start()
        self._idle_task = asyncio.create_task(self._idle_watchdog())

    async def close(self) -> None:
        if self._idle_task is not None:
            self._idle_task.cancel()
            self._idle_task = None
        await self._close_context()
        await self._close_login_context()
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    async def _idle_watchdog(self) -> None:
        while True:
            try:
                await asyncio.sleep(30)
                idle = (
                    datetime.now(timezone.utc) - self._last_used
                ).total_seconds()
                if idle > IDLE_TIMEOUT_SECONDS and self._context is not None:
                    _LOGGER.info("Idle for %.0fs; closing browser context", idle)
                    async with self._lock:
                        await self._close_context()
                        if self._browser is not None:
                            await self._browser.close()
                            self._browser = None
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("idle watchdog error")

    # ---- browser + context -----------------------------------------------

    async def _ensure_browser(self) -> Browser:
        assert self._pw is not None, "BrowserManager.start() not called"
        if self._browser is not None and self._browser.is_connected():
            return self._browser
        launch_kwargs: dict = {
            "headless": False,  # rendered on Xvfb; lets the login page show up over noVNC
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
            ],
        }
        if self._settings.chromium_executable:
            launch_kwargs["executable_path"] = self._settings.chromium_executable
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        return self._browser

    async def _ensure_context(self) -> BrowserContext:
        if self._context is not None:
            return self._context
        browser = await self._ensure_browser()
        storage_state = (
            self._settings.storage_state_path
            if os.path.exists(self._settings.storage_state_path)
            else None
        )
        self._context = await browser.new_context(
            storage_state=storage_state,
            user_agent=self._settings.user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        await self._context.add_init_script(_WEBDRIVER_SHIM)
        return self._context

    async def _close_context(self) -> None:
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:  # pragma: no cover
                _LOGGER.exception("error closing context")
            self._context = None

    async def _save_storage_state(self, ctx: BrowserContext) -> None:
        Path(self._settings.storage_state_path).parent.mkdir(
            parents=True, exist_ok=True
        )
        await ctx.storage_state(path=self._settings.storage_state_path)

    # ---- session probe ---------------------------------------------------

    async def is_logged_in(self) -> bool:
        if not os.path.exists(self._settings.storage_state_path):
            return False
        async with self._lock:
            self._last_used = datetime.now(timezone.utc)
            ctx = await self._ensure_context()
            page = await ctx.new_page()
            try:
                await page.goto(
                    f"{self._settings.base_url}/gp/your-account/order-history",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                logged_in = not self._is_signin_url(page.url)
                if logged_in:
                    await self._save_storage_state(ctx)
                return logged_in
            finally:
                await page.close()

    @staticmethod
    def _is_signin_url(url: str) -> bool:
        return any(marker in url for marker in SIGNIN_PATH_MARKERS)

    # ---- scrape page context ---------------------------------------------

    @asynccontextmanager
    async def scrape_page(self) -> AsyncIterator[Page]:
        """Yield a Page for scraping. Raises LoginRequiredError if redirected."""
        async with self._lock:
            self._last_used = datetime.now(timezone.utc)
            ctx = await self._ensure_context()
            page = await ctx.new_page()
            try:
                yield page
                # Save refreshed cookies after a successful scrape flow.
                await self._save_storage_state(ctx)
                self.last_scrape_at = datetime.now(timezone.utc)
            finally:
                try:
                    await page.close()
                except Exception:  # pragma: no cover
                    pass

    async def goto(self, page: Page, url: str, *, timeout: int = 45_000) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        if self._is_signin_url(page.url):
            raise LoginRequiredError(f"redirected to sign-in: {page.url}")
        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            # Amazon pages often never reach networkidle due to long-poll beacons; ignore.
            pass

    # ---- login flow (headed) ---------------------------------------------

    async def open_login(self) -> None:
        """Open a visible Chromium window on Xvfb at the Amazon sign-in page.

        Uses a separate context with no stored state so a fresh login is
        captured. The caller watches for completion via login_in_progress().
        """
        await self._close_login_context()
        browser = await self._ensure_browser()
        self._login_context = await browser.new_context(
            user_agent=self._settings.user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        await self._login_context.add_init_script(_WEBDRIVER_SHIM)
        self._login_page = await self._login_context.new_page()
        await self._login_page.goto(
            f"{self._settings.base_url}/ap/signin",
            wait_until="domcontentloaded",
        )
        asyncio.create_task(self._watch_login_complete())

    async def _watch_login_complete(self) -> None:
        """Poll the login page; when it lands on an authenticated URL, save state."""
        if self._login_page is None or self._login_context is None:
            return
        try:
            for _ in range(60 * 15):  # up to 15 minutes
                await asyncio.sleep(1)
                if self._login_page.is_closed():
                    break
                url = self._login_page.url
                if url and "amazon" in url and not self._is_signin_url(url):
                    await self._save_storage_state(self._login_context)
                    _LOGGER.info("Login captured; storage_state saved")
                    # Reset scraping context so it picks up the new state on next call.
                    await self._close_context()
                    break
        finally:
            await self._close_login_context()

    async def _close_login_context(self) -> None:
        if self._login_page is not None:
            try:
                await self._login_page.close()
            except Exception:  # pragma: no cover
                pass
            self._login_page = None
        if self._login_context is not None:
            try:
                await self._login_context.close()
            except Exception:  # pragma: no cover
                pass
            self._login_context = None

    @property
    def login_in_progress(self) -> bool:
        return self._login_context is not None

    async def clear_session(self) -> None:
        async with self._lock:
            await self._close_context()
            await self._close_login_context()
            try:
                os.remove(self._settings.storage_state_path)
            except FileNotFoundError:
                pass
