"""Propose the latest Chrome for Testing Stable linux64 build from a clean default-branch checkout."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


FEED = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
BRANCH = "deps/chromium-stable"
PIN = "CHROME_VERSION"


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", value):
        raise ValueError(f"Invalid four-part Chrome version: {value!r}")
    return tuple(map(int, value.split(".")))


def stable_build():
    stable = json.loads(command("curl", "-fsSL", "--retry", "2", "--max-time", "30", FEED))["channels"]["Stable"]
    candidate = stable["version"]
    version(candidate)
    url = f"https://storage.googleapis.com/chrome-for-testing-public/{candidate}/linux64/chrome-linux64.zip"
    downloads = [item["url"] for item in stable["downloads"]["chrome"] if item["platform"] == "linux64"]
    if stable["channel"] != "Stable" or downloads != [url]:
        raise ValueError("Stable metadata does not identify the expected linux64 Chrome archive")
    return candidate, url


def check_archive(url):
    status = command("curl", "-fsSIL", "--retry", "2", "--max-time", "30",
                     "--output", os.devnull, "--write-out", "%{http_code}", url)
    if status != "200":
        raise ValueError(f"Expected HTTP 200 for {url}, got {status}")


def latest_pr(repo, base, state):
    owner = repo.split("/")[0]
    pulls = json.loads(command("gh", "api", "--method", "GET", f"repos/{repo}/pulls",
                               "-f", f"head={owner}:{BRANCH}", "-f", f"base={base}", "-f", f"state={state}",
                               "-f", "sort=created", "-f", "direction=desc", "-f", "per_page=1"))
    return pulls[0] if pulls else None


def update(repo, base):
    candidate, url = stable_build()
    target = version(candidate)
    base_ref = f"refs/remotes/origin/{base}"
    current = command("git", "show", f"{base_ref}:{PIN}")
    if target <= version(current):
        return

    tracking_ref = f"refs/remotes/origin/{BRANCH}"
    old_head = command("git", "for-each-ref", "--format=%(objectname)", tracking_ref)
    pending = version(command("git", "show", f"{old_head}:{PIN}")) if old_head else None

    pr = latest_pr(repo, base, "open")
    if pr and pr["head"]["sha"] != old_head:
        raise RuntimeError("The update branch changed after checkout. Retry with a fresh checkout.")
    if not pr:
        closed = latest_pr(repo, base, "closed")
        if closed and closed["merged_at"] is None:
            # The bot branch can be deleted or reused after dismissal. Read the pin at the closed PR's head.
            dismissed = command("gh", "api", "--method", "GET", f"repos/{repo}/contents/{PIN}",
                                "-f", f"ref={closed['head']['sha']}", "-H", "Accept: application/vnd.github.raw+json")
            if target <= version(dismissed):
                return
        if closed and closed["head"]["sha"] == old_head:
            pending = None  # A leftover branch from a completed PR is no longer a pending proposal.
    if pending is not None and target < pending:
        return

    title = f"Update Chromium to {candidate}"
    body = (f"Update the Chrome for Testing Stable linux64 build from `{current}` to `{candidate}`.\n\n"
            f"[Official build feed]({FEED}) · [Download the linux64 archive]({url})")
    if pending == target and pr:
        # Only repair an interrupted refresh. Leave reviewers' edits alone on an unchanged proposal.
        previous_title = re.fullmatch(r"Update Chromium to ([0-9]+(?:\.[0-9]+){3})", pr["title"])
        if not previous_title or target <= version(previous_title[1]):
            return

    check_archive(url)
    if pending != target:
        command("git", "switch", "--detach", base_ref)
        Path(PIN).write_text(candidate)
        command("git", "-c", "user.name=ferret-release[bot]", "-c",
                "user.email=ferret-release[bot]@users.noreply.github.com", "commit", "-m", title, "--", PIN)
        ref = f"refs/heads/{BRANCH}"
        command("git", "push", f"--force-with-lease={ref}:{old_head}", "origin", f"HEAD:{ref}")
    elif command("git", "diff", "--name-only", f"{base_ref}...{old_head}") != PIN:
        raise RuntimeError(f"Refusing to propose changes outside {PIN} from {BRANCH}")

    # Also finish creating/updating PR metadata if a previous run stopped just after pushing.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as description:
        description.write(body)
        description.flush()
        action = ["edit", str(pr["number"])] if pr else ["create", "--base", base, "--head", BRANCH]
        print(command("gh", "pr", *action, "--repo", repo, "--title", title, "--body-file", description.name))


if __name__ == "__main__":
    update(os.environ["GITHUB_REPOSITORY"], os.environ["DEFAULT_BRANCH"])
