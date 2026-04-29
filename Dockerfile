FROM debian:bookworm-slim

ARG IMAGE_VERSION=dev
ARG CHROME_VERSION=stable
ARG CHROME_CHANNEL=Stable
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

LABEL org.opencontainers.image.title="Ferret Browser"
LABEL org.opencontainers.image.description="Headless Chrome browser image for Ferret/CDP automation"
LABEL org.opencontainers.image.version="${IMAGE_VERSION}"
LABEL org.opencontainers.image.vendor="MontFerret"
LABEL org.opencontainers.image.url="https://www.montferret.dev/"
LABEL org.opencontainers.image.source="https://github.com/MontFerret/ferret"
LABEL maintainer="MontFerret Team <mont.ferret@gmail.com>"
LABEL dev.montferret.chrome.version="${CHROME_VERSION}"
LABEL dev.montferret.chrome.channel="${CHROME_CHANNEL}"
LABEL dev.montferret.target.platform="${TARGETPLATFORM}"
LABEL dev.montferret.target.os="${TARGETOS}"
LABEL dev.montferret.target.arch="${TARGETARCH}"

EXPOSE 9222

ENV USER_DATA_DIR=/data
ENV DEBUG_ADDRESS=0.0.0.0
ENV DEBUG_PORT=9222
ENV CHROME_INTERNAL_PORT=9223
ENV CHROME_NO_SANDBOX=true
ENV CHROME_OPTS=""
ENV HOME=/home/ferret

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gosu \
    jq \
    socat \
    unzip \
    fonts-liberation \
    fonts-noto-color-emoji \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 -s /bin/bash ferret \
    && mkdir -p /data /home/ferret/.cache \
    && chown -R ferret:ferret /data /home/ferret

RUN set -eux; \
    if [ "${TARGETARCH:-amd64}" != "amd64" ]; then \
      echo "Chrome for Testing linux64 requires linux/amd64, got TARGETARCH=${TARGETARCH:-unknown}"; \
      exit 1; \
    fi; \
    if [ "$CHROME_VERSION" = "stable" ]; then \
      resolved_version="$(curl -fsSL https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json \
        | jq -r --arg channel "$CHROME_CHANNEL" '.channels[$channel].version')"; \
    else \
      resolved_version="$CHROME_VERSION"; \
    fi; \
    test -n "$resolved_version"; \
    echo "$resolved_version" > /opt/chrome-version; \
    url="https://storage.googleapis.com/chrome-for-testing-public/${resolved_version}/linux64/chrome-linux64.zip"; \
    curl -fsSL "$url" -o /tmp/chrome-linux64.zip; \
    unzip /tmp/chrome-linux64.zip -d /opt; \
    rm /tmp/chrome-linux64.zip; \
    ln -s /opt/chrome-linux64/chrome /usr/local/bin/chrome; \
    chrome --version || true

COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]