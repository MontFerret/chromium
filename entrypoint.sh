#!/bin/bash
set -e

# https://kapeli.com/cheat_sheets/Chromium_Command_Line_Switches.docset/Contents/Resources/Documents/index
CHROME_ARGS="--disable-background-networking \
--disable-background-timer-throttling \
--disable-breakpad \
--disable-canvas-aa \
--disable-client-side-phishing-detection \
--disable-cloud-import \
--disable-composited-antialiasing \
--disable-default-apps \
--disable-demo-mode \
--disable-dev-shm-usage \
--disable-extensions \
--disable-hang-monitor \
--disable-gesture-typing \
--disable-gpu \
--disable-gpu-sandbox \
--disable-infobars \
--disable-kill-after-bad-ipc \
--disable-notifications \
--disable-offer-store-unmasked-wallet-cards \
--disable-offer-upload-credit-cards \
--disable-office-editing-component-extension \
--disable-password-generation \
--disable-print-preview \
--disable-prompt-on-repost \
--disable-renderer-backgrounding \
--disable-seccomp-filter-sandbox \
--disable-setuid-sandbox \
--disable-smooth-scrolling \
--disable-speech-api \
--disable-sync \
--disable-tab-for-desktop-share \
--disable-translate \
--disable-voice-input \
--disable-wake-on-wifi \
--disable-web-security \
--disk-cache-dir=/tmp/cache-dir \
--disk-cache-size=10000000 \
--enable-async-dns \
--enable-simple-cache-backend \
--enable-tcp-fast-open \
--enable-webgl \
--font-render-hinting=none \
--headless \
--hide-scrollbars \
--ignore-certificate-errors \
--ignore-certificate-errors-spki-list \
--ignore-gpu-blocklist \
--ignore-ssl-errors \
--log-level=0 \
--media-cache-size=10000000 \
--metrics-recording-only \
--mute-audio \
--no-default-browser-check \
--no-experiments \
--no-first-run \
--no-pings \
--no-sandbox \
--no-zygote \
--prerender-from-omnibox=disabled \
--remote-debugging-address=$DEBUG_ADDRESS \
--remote-debugging-port=$DEBUG_PORT \
--safebrowsing-disable-auto-update \
--use-gl=swiftshader \
--user-data-dir=$HOME"

if [ -n "$CHROME_OPTS" ]; then
  CHROME_ARGS="${CHROME_ARGS} ${CHROME_OPTS}"
fi

# Start Chrome
exec sh -c "chrome $CHROME_ARGS"