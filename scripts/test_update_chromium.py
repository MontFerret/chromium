import contextlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import update_chromium as updater


def feed(version):
    url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/linux64/chrome-linux64.zip"
    return {"channels": {"Stable": {"channel": "Stable", "version": version, "downloads": {
        "chrome": [{"platform": "linux64", "url": url}],
    }}}}


class UpdateTest(unittest.TestCase):
    @staticmethod
    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    def setUp(self):
        self.enterContext(contextlib.chdir(self.enterContext(tempfile.TemporaryDirectory())))
        self.git("init", "--quiet", "-b", "main")
        self.git("init", "--quiet", "--bare", "remote.git")
        self.git("remote", "add", "origin", "remote.git")
        Path(updater.PIN).write_text("151.0.7922.9")
        self.git("add", updater.PIN)
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Initial pin")
        self.git("push", "-q", "origin", "main")
        self.metadata = feed("151.0.7922.10")
        self.archive_status = "200"
        self.archive_checks = []
        self.pr_writes = []
        self.open_pr = None
        self.closed_pr = None
        self.enterContext(patch.object(updater, "command", self.command))

    def head(self):
        return self.git("for-each-ref", "--format=%(objectname)", "refs/remotes/origin/" + updater.BRANCH)

    def command(self, *args):
        if args[0] == "git":
            return self.git(*args[1:])
        if args[0] == "curl":
            if args[-1] == updater.FEED:
                return json.dumps(self.metadata)
            self.archive_checks.append(args[-1])
            return self.archive_status
        if args[:2] == ("gh", "api"):
            if "repos/MontFerret/chromium/pulls" in args:
                self.assertIn("head=MontFerret:" + updater.BRANCH, args)
                self.assertIn("base=main", args)
                pr = self.open_pr if "state=open" in args else self.closed_pr
                if pr is self.open_pr and pr:
                    pr["head"] = {"sha": self.head()}
                return json.dumps([pr] if pr else [])
            self.assertIn("repos/MontFerret/chromium/contents/CHROME_VERSION", args)
            self.assertIn(f"ref={self.closed_pr['head']['sha']}", args)
            return self.git("show", f"{self.closed_pr['head']['sha']}:{updater.PIN}")

        self.assertEqual(args[:2], ("gh", "pr"))
        self.assertEqual(args[2], "edit" if self.open_pr else "create")
        self.pr_writes.append(args[2])
        self.open_pr = {
            "number": 1, "head": {"sha": self.head()}, "title": args[args.index("--title") + 1],
            "body": Path(args[args.index("--body-file") + 1]).read_text(),
        }
        return "PR #1"

    def check(self):
        updater.update("MontFerret/chromium", "main")

    def test_create_refresh_and_repeat(self):
        self.check()
        first = self.head()
        self.assertEqual(self.git("diff", "--name-only", "main..." + first), updater.PIN)
        self.assertEqual(self.git("show", first + ":CHROME_VERSION"), "151.0.7922.10")
        self.assertIn("151.0.7922.9", self.open_pr["body"])
        self.assertIn(self.archive_checks[0], self.open_pr["body"])
        self.open_pr["title"] = "Reviewer annotation"
        self.check()
        self.assertEqual(self.head(), first)
        self.assertEqual(len(self.archive_checks), 1)

        self.metadata = feed("152.0.1.0")
        self.check()
        self.assertNotEqual(self.head(), first)
        self.assertEqual(self.git("diff", "--name-only", "main..." + self.head()), updater.PIN)
        self.assertIn("152.0.1.0", self.open_pr["title"])
        self.assertIn("152.0.1.0", self.open_pr["body"])
        self.check()
        self.metadata = feed("151.0.7922.11")  # Feed regresses while a newer proposal is open.
        self.check()
        self.assertEqual(self.pr_writes, ["create", "edit"])
        self.assertEqual(len(self.archive_checks), 2)

    def test_dismissed_version_survives_branch_deletion(self):
        self.check()
        self.closed_pr = dict(self.open_pr, merged_at=None)
        self.open_pr = None
        self.git("push", "-q", "origin", "--delete", updater.BRANCH)
        self.check()
        self.assertFalse(self.head())
        self.assertEqual(self.pr_writes, ["create"])
        self.metadata = feed("151.0.7922.11")
        self.check()
        self.assertEqual(self.pr_writes, ["create", "create"])

    def test_retry_after_push_without_another_commit(self):
        self.check()
        first = self.head()
        self.open_pr = None  # PR creation failed after push.
        self.check()
        self.assertEqual(self.head(), first)
        old_title = self.open_pr["title"]
        self.metadata = feed("152.0.0.1")
        self.check()
        second = self.head()
        self.open_pr["title"] = old_title  # PR edit failed after push.
        self.check()
        self.assertEqual(self.head(), second)
        self.assertEqual(self.open_pr["title"], "Update Chromium to 152.0.0.1")
        self.assertEqual(self.pr_writes, ["create", "create", "edit", "edit"])

    def test_orphan_branch_with_other_changes_cannot_be_proposed(self):
        self.check()
        self.open_pr = None
        Path("other").touch()
        self.git("add", "other")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Other change")
        self.git("push", "-q", "origin", "HEAD:refs/heads/" + updater.BRANCH)
        with self.assertRaisesRegex(RuntimeError, "outside CHROME_VERSION"):
            self.check()
        self.assertEqual(self.pr_writes, ["create"])

    def test_equal_and_older_pin(self):
        for value in ("151.0.7922.9", "150.99.9999.99"):
            self.metadata = feed(value)
            self.check()
        self.assertFalse(self.head())
        self.assertFalse(self.archive_checks)
        self.assertFalse(self.pr_writes)

    def test_invalid_metadata_and_unavailable_download(self):
        missing = feed("152.0.0.1")
        missing["channels"]["Stable"]["downloads"]["chrome"].clear()
        wrong_url = feed("152.0.0.1")
        wrong_url["channels"]["Stable"]["downloads"]["chrome"][0]["url"] = "https://example.com/wrong.zip"
        for metadata in (feed("152.0.1"), feed("152.0.x.1"), missing, wrong_url):
            self.metadata = metadata
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                self.check()
        self.assertFalse(self.archive_checks)
        self.metadata = feed("152.0.0.1")
        self.archive_status = "404"
        with self.assertRaises(ValueError):
            self.check()
        self.assertFalse(self.head())
        self.assertFalse(self.pr_writes)
