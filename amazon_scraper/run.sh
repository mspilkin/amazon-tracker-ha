#!/usr/bin/env bashio
# Add-on entrypoint. Launches Xvfb + fluxbox + x11vnc + noVNC, then the FastAPI service.
set -e

AMAZON_DOMAIN="$(bashio::config 'amazon_domain')"
HISTORY_MONTHS="$(bashio::config 'history_months')"
LOG_LEVEL="$(bashio::config 'log_level')"

export AMAZON_DOMAIN HISTORY_MONTHS
export SCRAPER_LOG_LEVEL="${LOG_LEVEL}"

mkdir -p /data /share/amazon_tracker/debug

# ---- Xvfb -----------------------------------------------------------------
bashio::log.info "Starting Xvfb on ${DISPLAY} at ${XVFB_RESOLUTION}"
Xvfb "${DISPLAY}" -screen 0 "${XVFB_RESOLUTION}" -nolisten tcp -ac &

for _ in $(seq 1 30); do
  if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    bashio::log.info "Xvfb ready"
    break
  fi
  sleep 0.2
done

if ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
  bashio::log.fatal "Xvfb failed to come up on ${DISPLAY}"
  exit 1
fi

# ---- fluxbox + x11vnc -----------------------------------------------------
bashio::log.info "Starting fluxbox"
DISPLAY="${DISPLAY}" fluxbox >/tmp/fluxbox.log 2>&1 &

bashio::log.info "Starting x11vnc on :${VNC_PORT}"
x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -forever -shared -nopw -quiet -bg \
       -o /tmp/x11vnc.log

# ---- noVNC (websockify) ---------------------------------------------------
# Bind to all interfaces so HA ingress can reach us. Default varies by version
# of websockify and has burned us before.
bashio::log.info "Starting noVNC/websockify on 0.0.0.0:${NOVNC_PORT}"
websockify --web=/usr/share/novnc \
           --heartbeat=30 \
           "0.0.0.0:${NOVNC_PORT}" \
           "127.0.0.1:${VNC_PORT}" >/tmp/websockify.log 2>&1 &
WEBSOCKIFY_PID=$!

# Verify websockify is actually listening before we cede control to uvicorn.
for _ in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:${NOVNC_PORT}/" -o /dev/null 2>&1; then
    bashio::log.info "noVNC reachable"
    break
  fi
  sleep 0.2
done

if ! curl -sf "http://127.0.0.1:${NOVNC_PORT}/" -o /dev/null 2>&1; then
  bashio::log.error "noVNC did not come up on port ${NOVNC_PORT}; dumping log:"
  cat /tmp/websockify.log || true
fi

# ---- FastAPI scraper ------------------------------------------------------
bashio::log.info "Starting scraper API on 0.0.0.0:${API_PORT}"
cd /opt/scraper
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${API_PORT}" \
  --log-level "${SCRAPER_LOG_LEVEL}"
