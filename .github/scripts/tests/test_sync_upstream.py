"""Exercise the upstream-sync whitespace gate with real Git merge indexes.

The parent repository tracks XML manifests with CRLF line endings.  Accepting
those carriage returns must not disable checks for actual trailing whitespace
or accidentally committed conflict markers.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/sync-upstream.yml"
GATE = ("-c", "core.whitespace=cr-at-eol", "diff", "--cached", "--check")


@unittest.skipUnless(shutil.which("git"), "Git is required for merge-index regression tests")
class SyncWhitespaceGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sync-upstream-test-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.env = os.environ.copy()
        # User/system Git settings must not normalize the fixture's bytes or
        # change which whitespace errors Git diagnoses.
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.env["GIT_CONFIG_GLOBAL"] = os.devnull
        self.git("init", "--initial-branch=NoMount")
        self.git("config", "user.name", "Sync regression test")
        self.git("config", "user.email", "sync-test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "core.whitespace", "blank-at-eol,blank-at-eof,space-before-tab")
        (self.repo / "README.md").write_bytes(b"Base commit\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "base")

    def git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ("git", *arguments),
            cwd=self.repo,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode:
            self.fail(
                f"git {' '.join(arguments)} failed ({result.returncode}):\n"
                + result.stdout.decode("utf-8", errors="replace")
                + result.stderr.decode("utf-8", errors="replace")
            )
        return result

    def merge_upstream_manifest(self, contents: bytes) -> None:
        self.git("switch", "-c", "upstream")
        manifest = self.repo / "manifests/a16/oneplus_13s_6.6.89_w.xml"
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes(contents)
        self.git("add", "--", str(manifest.relative_to(self.repo)))
        self.git("commit", "-m", "upstream manifest update")
        self.git("switch", "NoMount")
        self.git("merge", "--no-ff", "--no-commit", "upstream")
        self.git("rev-parse", "--verify", "MERGE_HEAD")
        staged = self.git("show", ":manifests/a16/oneplus_13s_6.6.89_w.xml").stdout
        self.assertEqual(staged, contents, "The fixture must preserve the upstream bytes")

    def test_upstream_crlf_manifest_passes_without_normalizing_it(self):
        self.merge_upstream_manifest(
            b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
            b"<manifest>\r\n"
            b'  <remote name="origin" fetch="https://github.com/OnePlusOSS/"/>\r\n'
            b"</manifest>\r\n"
        )
        old_gate = self.git("diff", "--cached", "--check", check=False)
        self.assertNotEqual(old_gate.returncode, 0)
        self.assertIn(b"trailing whitespace", old_gate.stdout)
        fixed_gate = self.git(*GATE, check=False)
        self.assertEqual(fixed_gate.returncode, 0, fixed_gate.stdout)

    def test_actual_trailing_space_before_crlf_is_rejected(self):
        self.merge_upstream_manifest(b"<manifest> \r\n</manifest>\r\n")
        result = self.git(*GATE, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"trailing whitespace", result.stdout)

    def test_actual_trailing_tab_before_crlf_is_rejected(self):
        self.merge_upstream_manifest(b"<manifest>\t\r\n</manifest>\r\n")
        result = self.git(*GATE, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"trailing whitespace", result.stdout)

    def test_accidentally_staged_conflict_markers_are_rejected(self):
        self.merge_upstream_manifest(
            b"<<<<<<< HEAD\r\n<manifest/>\r\n=======\r\n"
            b"<manifest></manifest>\r\n>>>>>>> upstream\r\n"
        )
        result = self.git(*GATE, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"conflict marker", result.stdout)


class SyncWorkflowContractTests(unittest.TestCase):
    def test_sync_uses_crlf_aware_gate_without_ignoring_check_failures(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        command = re.compile(
            r"^\s+git -c core\.whitespace=cr-at-eol diff --cached --check\s*$",
            re.MULTILINE,
        )
        self.assertEqual(len(command.findall(workflow)), 1)
        self.assertNotRegex(workflow, r"(?m)^\s+git diff --cached --check(?:\s|$)")
        self.assertNotIn("--ignore-space-at-eol", workflow)
        self.assertNotIn("--ignore-all-space", workflow)


if __name__ == "__main__":
    unittest.main()
