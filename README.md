# Amazon Tracker for Home Assistant

A Home Assistant custom integration + companion add-on that tracks Amazon
orders by scraping your buyer account with a Playwright-controlled headed
Chromium. Exposes order-count, delivery, and spend sensors entirely locally —
no cloud services.

**Status:** Phase 1 complete (scraper add-on MVP). Phase 2 (HA integration
skeleton) not started yet.

## Repository layout

```
.
├─ addon/amazon_scraper/          # HA add-on: Playwright + FastAPI + noVNC
│  ├─ app/                         # Python service
│  ├─ tests/                       # Parser unit tests (25 passing)
│  ├─ config.yaml                  # HA add-on manifest
│  ├─ Dockerfile
│  ├─ run.sh
│  └─ README.md                    # Install + API reference
└─ custom_components/amazon_tracker/   # HA integration (to be built in Phase 2)
```

## Phases

- **Phase 1 ✓** — Scraper add-on: Xvfb + noVNC, Playwright session, order-list
  and order-detail parsers, selector fallback table, parser test suite.
- **Phase 2** — HA integration: config flow, `DataUpdateCoordinator`, aiosqlite
  storage, order-count + delivery sensors, login/force-refresh services.
- **Phase 3** — Returns/refunds parsing, spend analytics sensors, category
  inference.
- **Phase 4** — Delivery photo download, rich entity attributes, HACS
  packaging, end-to-end verification.

See the [add-on README](addon/amazon_scraper/README.md) for install and usage
of the Phase 1 deliverable.
