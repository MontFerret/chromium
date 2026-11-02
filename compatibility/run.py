#!/usr/bin/env python3
"""Run the published Ferret HTML browser tests against a local Chromium image."""

import argparse
import base64
from contextlib import contextmanager
from functools import partial
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from PIL import Image

HERE = Path(__file__).resolve().parent
FERRET = "github.com/MontFerret/ferret/v2"
HTML = "github.com/MontFerret/contrib/modules/web/html"
LAB = "github.com/MontFerret/lab/v2"
STABLE = "ghcr.io/montferret/chromium:stable"
SMOKE = (
    "page/load.fql",
    "doc/input/input_by_css.fql",
    "doc/xpath/query.fql",
    "doc/click/click_by_css.fql",
    "page/navigation/stable_document.fql",
    "page/init_script/autonomous_reload.fql",
    "doc/iframes/input.fql",
    "doc/waitfor_event/network_request_finished_body.fql",
    "page/cookies/set.fql",
    "page/cookies/delete.fql",
)
STARTUP = "browser startup"
RENDER = ("compatibility/screenshot.fql", "compatibility/pdf.fql")


def output(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def prepare(work, args):
    go = partial(output, "go", env={**os.environ, "GOWORK": "off", "GOBIN": str(work)}, cwd=work)
    go("mod", "init", "montferret.dev/chromium/compat")
    versions = {}
    for module, pin in [(FERRET, args.ferret), (HTML, args.html)]:
        tags = json.loads(go("list", "-m", "-versions", "-json", module + "@latest"))["Versions"]
        if not tags or (pin and pin not in tags):
            raise ValueError(f"No matching published tag for {module}: {pin or 'latest'}")
        versions[module] = pin or tags[-1]
        print(f"{module} {versions[module]}", flush=True)
        go("mod", "edit", f"-require={module}@{versions[module]}")

    shutil.copy(HERE / "runtime.go", work)
    go("build", "-mod=mod", "-o", "runtime", ".")
    linked = [line.split() for line in go("version", "-m", "runtime").splitlines()]
    for module, version in versions.items():
        if not any(row[:3] == ["dep", module, version] for row in linked):
            raise ValueError(f"runtime does not contain {module}@{version}")

    tag = "modules/web/html/" + versions[HTML]
    repo = work / "contrib"
    subprocess.run(["git", "clone", "--quiet", "--depth=1", "--filter=blob:none", "--sparse",
                    "--branch", tag, "https://github.com/MontFerret/contrib.git", repo], check=True)
    output("git", "-C", repo, "sparse-checkout", "set", ".github/workflows", "tests/data/pages",
           "tests/modules/web/html/dynamic")
    ci = (repo / ".github/workflows/integration.yml").read_text()
    pins = set(re.findall(r"go install github\.com/MontFerret/lab/v2@(v[\w.-]+)", ci))
    if len(pins) != 1:
        raise ValueError(f"Expected one tagged Lab version in {tag}'s integration workflow")
    lab_version = pins.pop()
    print(f"contrib {tag} {output('git', '-C', repo, 'rev-parse', 'HEAD')}; Lab {lab_version}", flush=True)
    go("install", LAB + "@" + lab_version)

    suite = repo / "tests/modules/web/html/dynamic"
    cases = sorted(str(f.relative_to(suite)) for f in suite.rglob("*.fql"))
    if not cases:
        raise ValueError(f"No enabled FQL cases found in {tag}")
    if args.mode == "smoke":
        missing = set(SMOKE).difference(cases)
        if missing:
            raise ValueError(f"Missing smoke cases in {tag}: {sorted(missing)}")
        cases = list(SMOKE)

    # rc.24 uses this literal as both the input URL and the expected final URL.
    nav = suite / "doc/waitfor_event/navigation.fql"
    if nav.exists():
        nav.write_text(nav.read_text().replace('"https://getbootstrap.com/"',
                                               '(@lab.static.static + "/simple.html")'))
    (work / "compatibility").mkdir()
    for case in RENDER:
        shutil.copyfile(HERE.parent / case, work / case)
    return cases + list(RENDER)


@contextmanager
def browser(image):
    command = ["docker", "create", "--platform", "linux/amd64", "-p", "127.0.0.1::9222"]
    if sys.platform.startswith("linux"):
        command += ["--add-host", "host.docker.internal:host-gateway"]
    container = output(*command, image)
    try:
        yield container
    finally:
        subprocess.run(["docker", "logs", "--tail", "150", container], check=False)
        subprocess.run(["docker", "rm", "-fv", container], check=True, stdout=subprocess.DEVNULL)


def startup(endpoint, expected):
    deadline = time.monotonic() + 45
    while True:
        try:
            with urlopen(endpoint + "/json/version", timeout=2) as response:
                payload = json.load(response)
                if not isinstance(payload, dict) or not isinstance(payload.get("Browser"), str):
                    raise ValueError("DevTools response is missing its Browser version")
                version = payload["Browser"]
            break
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise ValueError(f"DevTools did not become ready: {exc}") from exc
            time.sleep(0.25)
    print(f"DevTools {version}; expected {expected}", flush=True)
    if version.rsplit("/", 1)[-1] != expected:
        raise ValueError(f"expected Chromium {expected}, got {version}")


def check_render(work, case, env):
    result = subprocess.run([work / "runtime"], input=(work / case).read_bytes(),
                            capture_output=True, env=env, timeout=120)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace"))
    encoded = json.loads(result.stdout)
    if not isinstance(encoded, str):
        raise ValueError("expected a base64-encoded artifact from Ferret")
    data = base64.b64decode(encoded, validate=True)
    if case.endswith("screenshot.fql"):
        with Image.open(io.BytesIO(data)) as png:
            png.load()
            if png.format != "PNG" or png.size != (160, 90):
                raise ValueError(f"expected 160x90 PNG, got {png.format} {png.size}")
        return

    if not data.startswith(b"%PDF-"):
        raise ValueError("missing PDF header")
    info = subprocess.check_output(["pdfinfo", "-"], input=data, env={**env, "LC_ALL": "C"}, timeout=10)
    if not re.search(rb"^Pages:\s+[1-9]\d*\s*$", info, re.MULTILINE):
        raise ValueError("PDF has no pages")


def check_case(work, case, env):
    runtime = work / "runtime"
    if case in RENDER:
        check_render(work, case, env)
        return

    tests = work / "contrib/tests"
    command = [work / "lab", "run", "--runtime=bin://" + str(runtime), "--reporter=simple",
               "--timeout=120", "--attempts=1", "--times=1", "--concurrency=1",
               "--serve-bind=0.0.0.0", "--serve-host=host.docker.internal",
               "--serve=" + str(tests / "data/pages/static"), "--serve=" + str(tests / "data/pages/dynamic"),
               "--files=" + str(tests / "modules/web/html/dynamic" / case)]
    result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=135)
    if result.returncode or not re.search(r"^DONE passed=1 failed=0 ", result.stdout, re.MULTILINE):
        raise ValueError(result.stdout.strip() or f"Lab exited with status {result.returncode}")


def run_suite(work, image, expected, cases):
    failures = []
    with browser(image) as container:
        try:
            output("docker", "start", container, timeout=45)
            endpoint = "http://" + output("docker", "port", container, "9222/tcp")
            env = {**os.environ, "COMPAT_CDP_URL": endpoint}
            startup(endpoint, expected)
            # A working discovery endpoint alone doesn't prove Ferret can attach a target.
            output(work / "runtime", input='RETURN T::EQ(INNER_TEXT(PARSE("<h1>Ready</h1>"), "h1"), "Ready")',
                   env=env, timeout=120)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            print(f"FAIL {STARTUP}: {exc}", flush=True)
            return [STARTUP]
        print(f"PASS {STARTUP}", flush=True)
        for case in cases:
            try:
                check_case(work, case, env)
            except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
                failures.append(case)
                print(f"FAIL {case}: {exc}", flush=True)
            else:
                print(f"PASS {case}", flush=True)
    return failures


def image_info(image):
    info = json.loads(output("docker", "image", "inspect", image))[0]
    print(f"{image} {info['Id']} {info.get('RepoDigests') or []}", flush=True)
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["smoke", "full"])
    parser.add_argument("image", help="locally built linux/amd64 candidate")
    parser.add_argument("--ferret", help="exact published Ferret v2 tag")
    parser.add_argument("--html", help="exact published HTML module tag")
    args = parser.parse_args()
    if not shutil.which("pdfinfo"):
        parser.error("pdfinfo (Poppler) is required")

    expected = (HERE.parent / "CHROME_VERSION").read_text().strip()
    candidate = image_info(args.image)
    with tempfile.TemporaryDirectory(prefix="chromium-compat-") as directory:
        work = Path(directory).resolve()
        cases = prepare(work, args)
        print(f"Running {len(cases)} {args.mode} cases", flush=True)
        failed = run_suite(work, candidate["Id"], expected, cases)
        if not failed:
            print(f"All {len(cases)} cases passed.")
            return 0

        print(f"Candidate failed: {', '.join(failed)}. Comparing with {STABLE}", flush=True)
        subprocess.run(["docker", "pull", "--platform", "linux/amd64", STABLE], check=True)
        baseline = image_info(STABLE)
        baseline_version = baseline["Config"]["Labels"]["dev.montferret.chrome.version"]
        baseline_failed = run_suite(work, baseline["Id"], baseline_version, [f for f in failed if f != STARTUP])
        if STARTUP in baseline_failed and STARTUP not in failed:
            print("Comparison unavailable: stable failed browser startup.")
        else:
            for case in failed:
                scope = "both images" if case in baseline_failed else "candidate only"
                print(f"FAIL ({scope}): {case}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        sys.exit(f"Compatibility run failed: {error}")
