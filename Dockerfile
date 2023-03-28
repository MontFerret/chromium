FROM ubuntu:22.04

LABEL maintainer "MontFerret Team <mont.ferret@gmail.com>"
LABEL homepage "https://www.montferret.dev/"

EXPOSE 9222

# https://omahaproxy.appspot.com/
# https://chromiumdash.appspot.com/releases?platform=Linux
ENV REVISION=1097615
ENV DOWNLOAD_HOST=https://storage.googleapis.com

RUN apt-get update -qqy \
  && DEBIAN_FRONTEND="noninteractive" apt-get -qqy install apt-transport-https inotify-tools gnupg \
    libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libcairo2 libcups2 \
    libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 \
    libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxss1 libxtst6 \
    libappindicator1 libnss3 libnss3-tools libasound2 libatk1.0-0 libc6 ca-certificates fonts-liberation \
    libatk-bridge2.0-0 libgbm1 lsb-release xdg-utils wget unzip \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

RUN wget -q -O chrome-linux.zip "$DOWNLOAD_HOST/chromium-browser-snapshots/Linux_x64/$REVISION/chrome-linux.zip" \
  && unzip chrome-linux.zip -d /usr/local \
  && rm chrome-linux.zip \
  && ln -s /usr/local/chrome-linux/chrome /usr/local/bin/chrome

RUN chrome --version

COPY entrypoint.sh /

RUN mkdir /data
VOLUME /data
ENV HOME=/data DEBUG_ADDRESS=0.0.0.0 DEBUG_PORT=9222

ENTRYPOINT ["/entrypoint.sh"]