"""Exercise the actual 5.15 SUSFS preparation on vendor trees with/without hooks."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / ".github/actions/build-kernel/action.yml"
BASH = os.environ.get("TEST_BASH") or shutil.which("bash")
BLK = "#include <trace/hooks/blk.h>\n"
MM = "#include <trace/hooks/mm.h>\n"
NAMESPACE = '#include "internal.h"\nvoid mount_hook(void) {}\n'
TASK_MMU = "#include <linux/pkeys.h>\nvoid memory_hook(void) {}\n"


def compatibility_blocks() -> tuple[str, str]:
    action = ACTION.read_text(encoding="utf-8")
    susfs = action.split("    - name: Apply SUSFS Patches\n", 1)[1]
    prepare, after_prepare = susfs.split('echo "apply-susfs:patch-source"', 1)
    postprocess = after_prepare.split('echo "apply-susfs:postprocess-source"', 1)[1]

    def profile(section: str) -> str:
        body = section.split("          android13-5.15)\n", 1)[1].split(
            "            ;;", 1
        )[0]
        return textwrap.dedent(body)

    return profile(prepare), profile(postprocess)


@unittest.skipUnless(BASH, "Bash is required to exercise the real build action")
class SusfsVendorHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="susfs-vendor-hooks-")
        self.addCleanup(self.temporary.cleanup)
        self.tree = Path(self.temporary.name)
        (self.tree / "fs/proc").mkdir(parents=True)
        self.namespace = self.tree / "fs/namespace.c"
        self.task_mmu = self.tree / "fs/proc/task_mmu.c"
        self.namespace.write_text(NAMESPACE, encoding="utf-8")
        self.task_mmu.write_text(TASK_MMU, encoding="utf-8")

    def apply_compatibility(self, sublevel: int) -> tuple[str, str]:
        before, after = compatibility_blocks()
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-s"],
            input=f"set -euo pipefail\nsublevel={sublevel}\n{before}\n{after}\ntrue\n",
            cwd=self.tree,
            env=os.environ.copy(),
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (
            self.namespace.read_text(encoding="utf-8"),
            self.task_mmu.read_text(encoding="utf-8"),
        )

    def test_n6x_197_does_not_gain_nonexistent_blk_header(self) -> None:
        self.assertEqual(self.apply_compatibility(197), (NAMESPACE, TASK_MMU))

    def test_206_without_vendor_hooks_does_not_gain_either_header(self) -> None:
        self.assertEqual(self.apply_compatibility(206), (NAMESPACE, TASK_MMU))

    def test_available_but_unused_headers_are_not_injected(self) -> None:
        headers = self.tree / "include/trace/hooks"
        headers.mkdir(parents=True)
        for name in ("blk.h", "mm.h"):
            (headers / name).write_text("/* unused hook header */\n", encoding="utf-8")
        self.assertEqual(self.apply_compatibility(206), (NAMESPACE, TASK_MMU))

    def test_197_preserves_existing_mount_hook_include_and_call(self) -> None:
        original = NAMESPACE.replace(
            "void mount_hook(void) {}", BLK + "void mount_hook(void) { android_vh_mount(); }"
        )
        self.namespace.write_text(original, encoding="utf-8")
        self.assertEqual(self.apply_compatibility(197), (original, TASK_MMU))

    def test_206_preserves_existing_mount_and_memory_hook_calls(self) -> None:
        original_namespace = NAMESPACE.replace(
            "void mount_hook(void) {}", BLK + "void mount_hook(void) { android_vh_mount(); }"
        )
        original_mmu = TASK_MMU.replace(
            "void memory_hook(void) {}", MM + "void memory_hook(void) { android_vh_mmu(); }"
        )
        self.namespace.write_text(original_namespace, encoding="utf-8")
        self.task_mmu.write_text(original_mmu, encoding="utf-8")
        self.assertEqual(
            self.apply_compatibility(206), (original_namespace, original_mmu)
        )

    def test_197_preserves_existing_memory_hook_include_and_call(self) -> None:
        original = TASK_MMU.replace(
            "void memory_hook(void) {}", MM + "void memory_hook(void) { android_vh_mmu(); }"
        )
        self.task_mmu.write_text(original, encoding="utf-8")
        self.assertEqual(self.apply_compatibility(197), (NAMESPACE, original))

    def test_old_vendor_tree_is_unchanged(self) -> None:
        self.assertEqual(self.apply_compatibility(149), (NAMESPACE, TASK_MMU))

    def test_second_application_does_not_duplicate_hook_includes(self) -> None:
        self.namespace.write_text(NAMESPACE.replace("\n", "\n" + BLK, 1), encoding="utf-8")
        self.task_mmu.write_text(TASK_MMU.replace("\n", "\n" + MM, 1), encoding="utf-8")
        first = self.apply_compatibility(206)
        self.assertEqual(self.apply_compatibility(206), first)
        self.assertEqual(first[0].count(BLK), 1)
        self.assertEqual(first[1].count(MM), 1)


if __name__ == "__main__":
    unittest.main()
