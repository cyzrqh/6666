"""Check the NFC fix and its y/m/n behavior with the kernel's own Kconfig tool."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "fix_oplus_nfc_dependency.py"
SPEC = importlib.util.spec_from_file_location("fix_oplus_nfc_dependency", SCRIPT)
assert SPEC and SPEC.loader
FIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIX)
NFC_CONFIG = ('config OPLUS_NFC\n'
              '   tristate "config oplus nfc chipset"\n'
              '   default y\n'
              '   help\n'
              '     get chipset version from dts.\n')
PROJECT_CONFIG = ('config OPLUS_FEATURE_OPROJECT\n'
                  '   tristate "Oplus project service"\n'
                  '   default n\n')
CONF = os.environ.get("KCONFIG_CONF")
ACTUAL_NFC = os.environ.get("NFC_KCONFIG")


class NfcDependencyRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="oplus-nfc-dependency-")
        self.addCleanup(self.temp.cleanup)
        self.tree = Path(self.temp.name)
        for path, content in (
            (FIX.NFC, NFC_CONFIG),
            (FIX.SOURCE, "void probe(void) { get_project(); get_Operator_Version(); }\n"),
            (FIX.PROVIDER, PROJECT_CONFIG),
        ):
            target = self.tree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def test_second_run_is_byte_identical(self) -> None:
        self.assertTrue(FIX.repair(self.tree))
        first = (self.tree / FIX.NFC).read_bytes()
        self.assertFalse(FIX.repair(self.tree))
        self.assertEqual((self.tree / FIX.NFC).read_bytes(), first)

    def test_unknown_provider_is_rejected_without_writing(self) -> None:
        before = (self.tree / FIX.NFC).read_bytes()
        (self.tree / FIX.PROVIDER).write_text("config DIFFERENT_PROVIDER\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            FIX.repair(self.tree)
        self.assertEqual((self.tree / FIX.NFC).read_bytes(), before)

    def test_unknown_calls_are_rejected_without_writing(self) -> None:
        before = (self.tree / FIX.NFC).read_bytes()
        (self.tree / FIX.SOURCE).write_text("void changed_probe(void) {}\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            FIX.repair(self.tree)
        self.assertEqual((self.tree / FIX.NFC).read_bytes(), before)

    def test_unrelated_kernel_without_oplus_nfc_is_unchanged(self) -> None:
        (self.tree / FIX.NFC).unlink()
        self.assertFalse(FIX.repair(self.tree))


@unittest.skipUnless(CONF and ACTUAL_NFC, "Requires the built kernel Kconfig tool and NFC Kconfig")
class NfcKconfigLinkTests(unittest.TestCase):
    def evaluate(self, provider: str | None, expected: str) -> None:
        with tempfile.TemporaryDirectory(prefix="oplus-nfc-kconfig-") as directory:
            root = Path(directory)
            config = root / ".config"
            top = root / "Kconfig"
            top.write_text(
                'config MODULES\n bool "Modules"\n modules\n default y\n'
                'config NFC\n bool "NFC core"\n default y\n'
                + (PROJECT_CONFIG if provider is not None else "")
                + f'source "{Path(ACTUAL_NFC).resolve().as_posix()}"\n',
                encoding="utf-8",
            )
            config.write_text(
                'CONFIG_MODULES=y\nCONFIG_NFC=y\nCONFIG_OPLUS_NFC=y\n'
                + (f'CONFIG_OPLUS_FEATURE_OPROJECT={provider}\n' if provider is not None else ""),
                encoding="utf-8",
            )
            env = dict(os.environ, KCONFIG_CONFIG=str(config))
            result = subprocess.run(
                [str(Path(CONF).resolve()), "--olddefconfig", str(top)],
                cwd=root, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            selected = config.read_text(encoding="utf-8")
            self.assertIn("CONFIG_MODULES=y\n", selected)
            self.assertIn("CONFIG_NFC=y\n", selected)
            if expected == "n":
                self.assertNotRegex(selected, r"(?m)^CONFIG_OPLUS_NFC=[ym]$")
            else:
                self.assertIn(f"CONFIG_OPLUS_NFC={expected}\n", selected)
            if provider in ("y", "m"):
                self.assertIn(f"CONFIG_OPLUS_FEATURE_OPROJECT={provider}\n", selected)

    def test_builtin_provider_keeps_builtin_nfc(self) -> None:
        self.evaluate("y", "y")

    def test_module_provider_cannot_be_used_by_builtin_nfc(self) -> None:
        self.evaluate("m", "m")

    def test_disabled_provider_does_not_get_forced_on(self) -> None:
        self.evaluate("n", "n")

    def test_missing_provider_cannot_leave_an_unlinkable_builtin(self) -> None:
        self.evaluate(None, "n")


if __name__ == "__main__":
    unittest.main()
