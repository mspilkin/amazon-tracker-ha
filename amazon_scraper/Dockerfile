ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV \
    LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    DISPLAY=:99 \
    XVFB_RESOLUTION=1920x1080x24 \
    NOVNC_PORT=6080 \
    VNC_PORT=5900 \
    API_PORT=8099 \
    STORAGE_STATE_PATH=/data/storage_state.json \
    DEBUG_DUMP_PATH=/share/amazon_tracker/debug

RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        x11-utils \
        fluxbox \
        novnc \
        websockify \
        python3 \
        python3-pip \
        ca-certificates \
        curl \
        jq \
        fonts-liberation \
        fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && python3 -m playwright install --with-deps chromium \
    && rm /tmp/requirements.txt

COPY app /opt/scraper/app
COPY run.sh /run.sh
COPY rootfs/usr/share/novnc/index.html /usr/share/novnc/index.html
RUN chmod a+x /run.sh

WORKDIR /opt/scraper
EXPOSE 6080 8099

CMD ["/run.sh"]
