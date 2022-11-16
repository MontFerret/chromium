# Chromium

The project provides a Docker image containing an optimized version of Chromium for scraping, profiling, or testing web pages.


## Running

```bash

# pull latest version from DockerHub Registry
$ docker pull montferret/chromium:latest

# pull latest version from GitHub Registry
$ docker pull ghcr.io/montferret/chromium:latest

# run
$ docker run -d -p 9222:9222 --name headless-chromium montferret/chromium
$ docker run -d -p 9222:9222 --name headless-chromium ghcr.io/montferret/chromium

# run with proxy

$ docker run -d -p 9222:9222 --name headless-chromium -e CHROME_OPTS='--proxy-server=my-proxy.com' montferret/chromium
$ docker run -d -p 9222:9222 --name headless-chromium -e CHROME_OPTS='--proxy-server=my-proxy.com' ghcr.io/montferret/chromium

```

## Using as a base image

When using ``montferret/chromium`` as a base image to build an image that runs your own program, you can experience zombie process problem. 
To reap zombie processeses, use dumb-init or tini on your Dockerfile's ENTRYPOINT:

```bash
FROM montferret/chromium:latest
...
# Install dumb-init
RUN apt install dumb-init
...
ENTRYPOINT ["dumb-init", "--"]
CMD ["/bin/sh", "-c", "./entrypoint.sh & YOUR_PROGRAM"]
```

If running Docker 1.13.0 or later, use docker run's --init arg instead to reap zombie processes.

```bash
docker run -d -p <PORT>:<PORT> --name <your-program> --init <your-image>
```
