#!/usr/bin/env bash
set -euo pipefail

: "${DEBUG_ADDRESS:=0.0.0.0}"
: "${DEBUG_PORT:=9222}"
: "${CHROME_INTERNAL_PORT:=9223}"
: "${USER_DATA_DIR:=/data}"
: "${CHROME_NO_SANDBOX:=true}"
: "${CHROME_OPTS:=}"

CHROME_HOST="127.0.0.1"

CHROME_ARGS="\
--headless=new \
--remote-debugging-address=$CHROME_HOST \
--remote-debugging-port=$CHROME_INTERNAL_PORT \
--user-data-dir=$USER_DATA_DIR \
--no-first-run \
--no-default-browser-check \
--disable-background-networking \
--disable-background-timer-throttling \
--disable-backgrounding-occluded-windows \
--disable-client-side-phishing-detection \
--disable-component-update \
--disable-default-apps \
--disable-dev-shm-usage \
--disable-domain-reliability \
--disable-extensions \
--disable-features=UseDBus,MediaRouter,OptimizationHints,AutofillServerCommunication,InterestFeedContentSuggestions \
--disable-hang-monitor \
--disable-prompt-on-repost \
--disable-renderer-backgrounding \
--disable-sync \
--metrics-recording-only \
--mute-audio \
--hide-scrollbars \
--safebrowsing-disable-auto-update \
--log-level=2"

if [ "$CHROME_NO_SANDBOX" = "true" ]; then
  CHROME_ARGS="$CHROME_ARGS --no-sandbox"
fi

if [ -n "$CHROME_OPTS" ]; then
  CHROME_ARGS="$CHROME_ARGS $CHROME_OPTS"
fi

mkdir -p "$USER_DATA_DIR"

start_proxy() {
  socat \
    "TCP-LISTEN:${DEBUG_PORT},bind=${DEBUG_ADDRESS},fork,reuseaddr" \
    "TCP:${CHROME_HOST}:${CHROME_INTERNAL_PORT}" &
}

if [ "$(id -u)" = "0" ]; then
  chown -R ferret:ferret "$USER_DATA_DIR" /home/ferret/.cache
  start_proxy
  exec gosu ferret sh -c "chrome $CHROME_ARGS about:blank"
else
  start_proxy
  exec sh -c "chrome $CHROME_ARGS about:blank"
fi