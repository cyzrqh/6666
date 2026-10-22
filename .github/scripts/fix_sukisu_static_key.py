#!/usr/bin/env python3
"""Match the pinned SukiSU sucompat switch to SUSFS's static-key callers.

SUSFS calls static_branch_likely() on this symbol. A bool with the same name
links successfully, but is not storage for a struct static_key_true. Keep the
original bool implementation when CONFIG_KSU_SUSFS is off.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SYMBOL = "ksu_su_compat_enabled"
C_PATH = Path("kernel/feature/sucompat.c")
H_PATH = Path("kernel/feature/sucompat.h")
NON_SUSFS_READ = """#else
__attribute__((hot)) static __always_inline bool __is_su_allowed(const void **ptr_to_check)
{
    if (!ksu_su_compat_enabled)
"""

# These are the actual b20dee702035af09cb2ecb5f35443bbc1747f3e6 snippets.
# Match the definition, feature reader/writer, and declaration as one contract;
# changing just the definition would break feature control and non-SUSFS builds.
REPLACEMENTS = {
    C_PATH: (
        (
            "bool ksu_su_compat_enabled __read_mostly = true;",
            "#ifdef CONFIG_KSU_SUSFS\n"
            "#include <linux/jump_label.h>\n"
            "DEFINE_STATIC_KEY_TRUE(ksu_su_compat_enabled);\n"
            "#else\n"
            "bool ksu_su_compat_enabled __read_mostly = true;\n"
            "#endif",
        ),
        (
            "    *value = ksu_su_compat_enabled ? 1 : 0;",
            "#ifdef CONFIG_KSU_SUSFS\n"
            "    *value = static_key_enabled(&ksu_su_compat_enabled) ? 1 : 0;\n"
            "#else\n"
            "    *value = ksu_su_compat_enabled ? 1 : 0;\n"
            "#endif",
        ),
        (
            "    ksu_su_compat_enabled = enable;",
            "#ifdef CONFIG_KSU_SUSFS\n"
            "    if (enable)\n"
            "        static_branch_enable(&ksu_su_compat_enabled);\n"
            "    else\n"
            "        static_branch_disable(&ksu_su_compat_enabled);\n"
            "#else\n"
            "    ksu_su_compat_enabled = enable;\n"
            "#endif",
        ),
    ),
    H_PATH: (
        (
            "extern bool ksu_su_compat_enabled;",
            "#ifdef CONFIG_KSU_SUSFS\n"
            "#include <linux/jump_label.h>\n"
            "extern struct static_key_true ksu_su_compat_enabled;\n"
            "#else\n"
            "extern bool ksu_su_compat_enabled;\n"
            "#endif",
        ),
    ),
}


def identifiers(source: str) -> int:
    """Count real references, not words in comments/string literals."""
    code = re.sub(
        r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        "",
        source,
        flags=re.DOTALL,
    )
    return len(re.findall(rf"\b{SYMBOL}\b", code))


def repair(ksu_root: Path) -> bool:
    if ksu_root.is_symlink():
        raise ValueError("refusing a symbolic-link SukiSU root")
    root = ksu_root.resolve()
    original: dict[Path, str] = {}
    for relative in REPLACEMENTS:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing or unsafe SukiSU source: {relative}")
        original[relative] = path.read_text(encoding="utf-8")

    states = [
        original[path].count(after)
        for path, pairs in REPLACEMENTS.items()
        for _, after in pairs
    ]
    if all(count == 1 for count in states):
        already_fixed = True
    elif all(count == 0 for count in states):
        already_fixed = False
    else:
        raise ValueError("partial or duplicated sucompat static-key repair")

    baseline = dict(original)
    if already_fixed:
        for path, pairs in REPLACEMENTS.items():
            for before, after in pairs:
                baseline[path] = baseline[path].replace(after, before, 1)

    for path, pairs in REPLACEMENTS.items():
        for before, _ in pairs:
            if baseline[path].count(before) != 1:
                raise ValueError(f"unknown SukiSU sucompat shape in {path}: {before.strip()}")

    # The remaining fourth C reference is inside the original !SUSFS sucompat
    # path. New direct users need a conscious compatibility update, not a guess.
    expected_counts = {C_PATH: 4, H_PATH: 1}
    for path, expected in expected_counts.items():
        if identifiers(baseline[path]) != expected:
            raise ValueError(f"unexpected sucompat switch reference in {path}")
    if baseline[C_PATH].count(NON_SUSFS_READ) != 1:
        raise ValueError("unknown non-SUSFS sucompat reader layout")
    for path in (root / "kernel").rglob("*"):
        if path.suffix not in {".c", ".h"} or not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative in REPLACEMENTS:
            continue
        if path.is_symlink():
            raise ValueError(f"refusing symbolic-link SukiSU source: {relative}")
        if identifiers(path.read_text(encoding="utf-8")):
            raise ValueError(f"unhandled sucompat switch reference in {relative}")

    if already_fixed:
        return False
    replacements = dict(original)
    for path, pairs in REPLACEMENTS.items():
        for before, after in pairs:
            replacements[path] = replacements[path].replace(before, after, 1)
    # Do not change either file until all declarations and users pass preflight.
    for relative, source in replacements.items():
        (root / relative).write_text(source, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ksu_root", type=Path)
    args = parser.parse_args()
    try:
        changed = repair(args.ksu_root)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"SukiSU static-key compatibility check failed: {exc}\n")
    print("Repaired SukiSU sucompat static key" if changed else "SukiSU sucompat static key already repaired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
