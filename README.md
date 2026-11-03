# Chromium

The project provides a Docker image containing an optimized version of Chromium for scraping, profiling, or testing web pages.
It's based on the official [Chromium builds](https://chromiumdash.appspot.com/releases) and includes additional dependencies for running in a headless mode.


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

## Testing a Chromium upgrade

The **Check for Chromium updates** workflow checks Google's Chrome for Testing Stable feed daily at 06:17 UTC. You can also run it manually on the default branch. When a newer `linux64` build is available, the workflow updates `CHROME_VERSION` in a single review PR on `deps/chromium-stable`. A later release refreshes that PR. Closing it without merging skips the proposed version until Google publishes a newer one. [Official build feed](https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json)

The updater uses the Ferret release GitHub App so the PR starts compatibility checks automatically. Install the App on this repository with Contents and Pull requests write access and make `FERRET_RELEASE_APP_CLIENT_ID` and `FERRET_RELEASE_APP_PRIVATE_KEY` available as Actions secrets.

Pull requests and pushes run a smoke suite through Ferret's HTML CDP driver. It checks browser startup, JavaScript-rendered content, CSS and XPath queries, input and clicks, navigation and reloads, iframes, network events, cookies, a decoded 160×90 PNG, and a PDF with at least one page.

To test locally, install Docker with `linux/amd64` support, Go, Git, Python 3 with Pillow, and Poppler's `pdfinfo`. Build the candidate and select a suite.

```sh
docker buildx build --platform linux/amd64 --load \
  --build-arg CHROME_VERSION="$(cat CHROME_VERSION)" -t montferret/chromium:ci .

python3 compatibility/run.py smoke montferret/chromium:ci
python3 compatibility/run.py full montferret/chromium:ci
```

The runner resolves the highest non-retracted Go module tags for Ferret v2 and HTML, including prereleases. It verifies the versions linked into the runtime, uses the HTML tag's FQL cases and fixture pages, and installs the Lab version specified by that tag. Each case runs once. The full suite includes upstream expected-failure cases. To replay a run, use the exact versions in its log.

```sh
python3 compatibility/run.py full montferret/chromium:ci \
  --ferret v2.0.0-alpha.61 --html v1.0.0-rc.24
```

Lab serves the upstream static pages and mock REST API with URLs reachable from the browser container. If a runtime stalls for 115 seconds, including during cleanup, it prints its active stage and goroutine stacks and exits with status 124 before Lab's 120-second limit.

On failure, the runner repeats the failing checks against the published GHCR `stable` image with the same runtime. CI saves the image identities, versions, per-case outcomes, runtime timeout diagnostics, and browser logs in the `chromium-compatibility-smoke` or `chromium-compatibility-full` artifact. A shared failure also blocks release.

Manually run the **Build and push Docker images** workflow to test a release artifact without publishing. On a published GitHub release, the workflow runs the full suite before copying the tested OCI archive to Docker Hub and GHCR. Stable releases also update the `latest` and `stable` aliases.
