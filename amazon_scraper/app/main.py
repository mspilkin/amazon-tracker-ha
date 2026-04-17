"""FastAPI surface for the Amazon scraper add-on."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .browser import BrowserManager, LoginRequiredError
from .config import load_settings
from .models import (
    HealthResponse,
    LoginOpenResponse,
    ScrapeRequest,
    ScrapeResult,
    SimpleStatus,
)
from .scrapers.orchestrator import Orchestrator

_LOGGER = logging.getLogger("amazon_scraper")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    logging.basicConfig(level=logging.INFO)
    browser = BrowserManager(settings)
    await browser.start()
    orchestrator = Orchestrator(settings, browser)
    app.state.settings = settings
    app.state.browser = browser
    app.state.orchestrator = orchestrator

    # Zero-terminal UX: if no session exists, auto-open Chromium at the Amazon
    # sign-in page so the user only has to click the sidebar to finish logging in.
    if not os.path.exists(settings.storage_state_path):
        _LOGGER.info("No storage_state.json; auto-opening login window")
        asyncio.create_task(browser.open_login())

    try:
        yield
    finally:
        await browser.close()


app = FastAPI(title="Amazon Scraper", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    browser: BrowserManager = app.state.browser
    settings = app.state.settings
    return HealthResponse(
        status="ok",
        logged_in=await browser.is_logged_in(),
        amazon_domain=settings.amazon_domain,
        browser_ready=True,
        last_scrape_at=browser.last_scrape_at,
        login_in_progress=browser.login_in_progress,
    )


@app.post("/login/open", response_model=LoginOpenResponse)
async def login_open() -> LoginOpenResponse:
    browser: BrowserManager = app.state.browser
    if browser.login_in_progress:
        return LoginOpenResponse(status="already_open", novnc_path="/")
    await browser.open_login()
    return LoginOpenResponse(status="opened", novnc_path="/")


@app.post("/login/cancel", response_model=SimpleStatus)
async def login_cancel() -> SimpleStatus:
    browser: BrowserManager = app.state.browser
    await browser._close_login_context()  # internal ok: service-level cancel
    return SimpleStatus(status="cancelled")


@app.post("/session/clear", response_model=SimpleStatus)
async def session_clear() -> SimpleStatus:
    browser: BrowserManager = app.state.browser
    await browser.clear_session()
    return SimpleStatus(status="cleared")


@app.post("/scrape/full", response_model=ScrapeResult)
async def scrape_full(req: ScrapeRequest) -> ScrapeResult:
    orchestrator: Orchestrator = app.state.orchestrator
    try:
        return await orchestrator.run_full(history_months=req.history_months)
    except LoginRequiredError as err:
        raise HTTPException(status_code=401, detail={"reason": "login_required", "url": str(err)})


@app.post("/scrape/incremental", response_model=ScrapeResult)
async def scrape_incremental(req: ScrapeRequest) -> ScrapeResult:
    orchestrator: Orchestrator = app.state.orchestrator
    try:
        return await orchestrator.run_incremental(
            active_order_ids=req.active_order_ids,
            since=req.since,
        )
    except LoginRequiredError as err:
        raise HTTPException(status_code=401, detail={"reason": "login_required", "url": str(err)})
