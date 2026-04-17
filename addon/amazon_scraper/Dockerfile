ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV \
    LANG=C.UTF-8 \
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

RUN apk add --no-cache \
        xvfb \
        xdpyinfo \
        x11vnc \
        fluxbox \
        novnc \
        websockify \
        chromium \
        nss \
        freetype \
        harfbuzz \
        ca-certificates \
        ttf-freefont \
        font-noto-emoji \
        dbus \
        py3-pip \
    && ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium-browser

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY app /opt/scraper/app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /opt/scraper
EXPOSE 6080 8099

CMD ["/run.sh"]
