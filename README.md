# Chromium

The project provides a Docker image containing an optimized version of Chromium for scraping, profiling, or testing web pages.


## Running

```bash

# pull latest version
$ docker pull montferret/chromium:latest

# pull specific tagged version
$ docker pull montferret/chromium:85.0.4182.0

# run
$ docker run -d -p 9222:9222 --rm --name headless-chromium montferret/chromium

# run with proxy

$ docker run -d -p 9222:9222 --rm --name headless-chromium -e CHROME_OPTS='--proxy-server=my-proxy.com' montferret/chromium

```

## Using as a base image

When using ``montferret/chromium`` as a base image to build an image that runs your own program, you can experience zombie process problem. To reap zombie processeses, use dumb-init or tini on your Dockerfile's ENTRYPOINT:

```bash
FROM montferret/chromium:latest
...
# Install dumb-init or tini
RUN apt install dumb-init
# or RUN apt install tini
...
ENTRYPOINT ["dumb-init", "--"]
# or ENTRYPOINT ["tini", "--"]
CMD ["/path/to/your/program"]
```

If running Docker 1.13.0 or later, use docker run's --init arg instead to reap zombie processes.

```bash
docker run -d -p <PORT>:<PORT> --name <your-program> --init <your-image>
```
