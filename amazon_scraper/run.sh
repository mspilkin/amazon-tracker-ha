#!/usr/bin/env bashio
# Add-on entrypoint. Launches Xvfb + fluxbox + x11vnc + noVNC, then the FastAPI service.
set -e

AMAZON_DOMAIN="$(bashio::config 'amazon_domain')"
HISTORY_MONTHS="$(bashio::config 'history_months')"
LOG_LEVEL="$(bashio::config 'log_level')"

export AMAZON_DOMAIN HISTORY_MONTHS
export SCRAPER_LOG_LEVEL="${LOG_LEVEL}"

mkdir -p /data /share/amazon_tracker/debug

bashio::log.info "Starting Xvfb on ${DISPLAY} at ${XVFB_RESOLUTION}"
Xvfb "${DISPLAY}" -screen 0 "${XVFB_RESOLUTION}" -nolisten tcp -ac &
XVFB_PID=$!

# Wait for X to be ready
for _ in $(seq 1 30); do
  if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then break; fi
  sleep 0.2
done

bashio::log.info "Starting fluxbox"
DISPLAY="${DISPLAY}" fluxbox >/dev/null 2>&1 &

bashio::log.info "Starting x11vnc on :${VNC_PORT}"
x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -forever -shared -nopw -quiet -bg

bashio::log.info "Starting noVNC on :${NOVNC_PORT}"
websockify --web=/usr/share/novnc "${NOVNC_PORT}" "localhost:${VNC_PORT}" &

bashio::log.info "Starting scraper API on :${API_PORT}"
cd /opt/scraper
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${API_PORT}" \
  --log-level "${SCRAPER_LOG_LEVEL}"
