#!/usr/bin/env bash
# Add-on entrypoint. Launches Xvfb + fluxbox + x11vnc + noVNC, then the FastAPI service.
set -eo pipefail

CONFIG_PATH=/data/options.json
AMAZON_DOMAIN="$(jq -r '.amazon_domain // "amazon.com"' "${CONFIG_PATH}" 2>/dev/null || echo amazon.com)"
HISTORY_MONTHS="$(jq -r '.history_months // 24' "${CONFIG_PATH}" 2>/dev/null || echo 24)"
LOG_LEVEL="$(jq -r '.log_level // "info"' "${CONFIG_PATH}" 2>/dev/null || echo info)"

# s6-overlay sometimes resets the environment when wrapping our CMD as a legacy
# service, so we default every env var defensively.
export DISPLAY="${DISPLAY:-:99}"
export XVFB_RESOLUTION="${XVFB_RESOLUTION:-1920x1080x24}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"
export VNC_PORT="${VNC_PORT:-5900}"
export API_PORT="${API_PORT:-8099}"
export STORAGE_STATE_PATH="${STORAGE_STATE_PATH:-/data/storage_state.json}"
export DEBUG_DUMP_PATH="${DEBUG_DUMP_PATH:-/share/amazon_tracker/debug}"
export AMAZON_DOMAIN HISTORY_MONTHS
export SCRAPER_LOG_LEVEL="${LOG_LEVEL}"

log() { echo "[$(date +%T)] $*"; }

mkdir -p /data /share/amazon_tracker/debug

log "Config: domain=${AMAZON_DOMAIN} months=${HISTORY_MONTHS} log=${LOG_LEVEL}"

# ---- Xvfb -----------------------------------------------------------------
log "Starting Xvfb on ${DISPLAY} at ${XVFB_RESOLUTION}"
Xvfb "${DISPLAY}" -screen 0 "${XVFB_RESOLUTION}" -nolisten tcp -ac &

for _ in $(seq 1 30); do
  if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    log "Xvfb ready"
    break
  fi
  sleep 0.2
done

if ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
  log "FATAL: Xvfb failed to come up on ${DISPLAY}"
  exit 1
fi

# ---- fluxbox + x11vnc -----------------------------------------------------
log "Starting fluxbox"
DISPLAY="${DISPLAY}" fluxbox >/tmp/fluxbox.log 2>&1 &

log "Starting x11vnc on :${VNC_PORT}"
x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -forever -shared -nopw -quiet -bg \
       -o /tmp/x11vnc.log

# ---- noVNC (websockify) ---------------------------------------------------
log "Starting noVNC/websockify on 0.0.0.0:${NOVNC_PORT}"
websockify --web=/usr/share/novnc \
           --heartbeat=30 \
           "0.0.0.0:${NOVNC_PORT}" \
           "127.0.0.1:${VNC_PORT}" >/tmp/websockify.log 2>&1 &

for _ in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:${NOVNC_PORT}/" -o /dev/null 2>&1; then
    log "noVNC reachable"
    break
  fi
  sleep 0.2
done

if ! curl -sf "http://127.0.0.1:${NOVNC_PORT}/" -o /dev/null 2>&1; then
  log "WARN: noVNC did not come up on port ${NOVNC_PORT}; dumping websockify log:"
  cat /tmp/websockify.log || true
fi

# ---- FastAPI scraper ------------------------------------------------------
log "Starting scraper API on 0.0.0.0:${API_PORT}"
cd /opt/scraper
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${API_PORT}" \
  --log-level "${SCRAPER_LOG_LEVEL}"
