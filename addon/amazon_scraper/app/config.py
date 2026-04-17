from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    amazon_domain: str
    history_months: int
    storage_state_path: str
    debug_dump_path: str
    api_port: int
    novnc_port: int
    display: str
    chromium_executable: str | None
    user_agent: str

    @property
    def base_url(self) -> str:
        return f"https://www.{self.amazon_domain}"


def load_settings() -> Settings:
    return Settings(
        amazon_domain=os.environ.get("AMAZON_DOMAIN", "amazon.com"),
        history_months=int(os.environ.get("HISTORY_MONTHS", "24")),
        storage_state_path=os.environ.get(
            "STORAGE_STATE_PATH", "/data/storage_state.json"
        ),
        debug_dump_path=os.environ.get(
            "DEBUG_DUMP_PATH", "/share/amazon_tracker/debug"
        ),
        api_port=int(os.environ.get("API_PORT", "8099")),
        novnc_port=int(os.environ.get("NOVNC_PORT", "6080")),
        display=os.environ.get("DISPLAY", ":99"),
        chromium_executable=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"),
        user_agent=os.environ.get(
            "SCRAPER_USER_AGENT",
            # Realistic desktop Chrome UA; keep fresh-ish to avoid sticking out.
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ),
    )
