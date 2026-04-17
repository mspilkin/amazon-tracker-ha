# Amazon Scraper Add-on

Playwright-driven headed Chromium that scrapes your Amazon account. Pairs with
the **Amazon Tracker** custom integration. Login is performed manually via
noVNC in your browser; the session is persisted so you only need to log in
again when Amazon invalidates the cookies.

## Install

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
   add this repo URL.
2. Install the **Amazon Scraper** add-on.
3. Configure options:
   - `amazon_domain` — e.g. `amazon.com`
   - `history_months` — how far back to scan (default 24)
   - `log_level` — `info` by default; bump to `debug` to troubleshoot
4. Start the add-on and open the **Amazon Login** panel from the sidebar
   (noVNC ingress). You should see a blank fluxbox desktop — the browser opens
   there when login is triggered.

## First login

From a terminal on the HA host or any host that can reach the add-on port:

```bash
# Replace <ADDON_HOST> with the add-on container hostname or HA host:port
curl -X POST http://<ADDON_HOST>:8099/login/open
```

Open the **Amazon Login** sidebar panel in HA. A Chromium window appears on
the virtual desktop pointing at Amazon sign-in. Complete username, password,
and 2FA as you normally would. When you land on the Amazon account home page,
the add-on saves `/data/storage_state.json` automatically.

Confirm:

```bash
curl http://<ADDON_HOST>:8099/health
# => {"status":"ok","logged_in":true, ...}
```

## Manual scrape smoke test

```bash
# Full scan using the configured history window
curl -X POST http://<ADDON_HOST>:8099/scrape/full \
     -H 'content-type: application/json' -d '{}' | jq '.orders | length'

# Incremental — only orders placed since a date
curl -X POST http://<ADDON_HOST>:8099/scrape/incremental \
     -H 'content-type: application/json' \
     -d '{"since":"2026-03-01","active_order_ids":[]}'
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + `logged_in` state |
| POST | `/login/open` | Launch a headed Chromium at Amazon sign-in on Xvfb |
| POST | `/login/cancel` | Close the login window without saving |
| POST | `/session/clear` | Delete `storage_state.json` |
| POST | `/scrape/full` | Scan the full configured history window |
| POST | `/scrape/incremental` | Re-check active orders + current year page 1 |

A 401 with `{"detail":{"reason":"login_required"}}` means the session has
expired; call `/login/open` again.

## Data & state locations

- `/data/storage_state.json` — persisted cookies + localStorage. Back this up
  if you want to avoid re-logging in after reinstall.
- `/share/amazon_tracker/debug/*.html` — raw HTML dumps written when the
  scraper detects zero cards on a page that previously had them (selector
  regression). Share these when reporting a layout break.

## Troubleshooting

- **Login panel shows only a grey screen** — give the browser 3–5 seconds to
  render after hitting `/login/open`. Refresh the panel if it stays blank.
- **`logged_in` stays `false` after login** — the watcher detects success by
  URL; some captcha or "choose an account" interstitials may delay it. Wait
  until you're on the Amazon homepage, then check `/health` again.
- **401 on every scrape** — run `POST /session/clear`, then repeat the login
  flow.
- **Zero orders returned** — check `/share/amazon_tracker/debug/` for a dumped
  HTML file and compare against the fixtures in `tests/fixtures/`. Selector
  hotfixes go in `app/scrapers/selectors.py`; bump `SELECTOR_VERSION`.

## Local development

```bash
cd addon/amazon_scraper
python -m pip install -r requirements.txt pytest
python -m pytest tests/
```
