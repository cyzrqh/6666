#!/usr/bin/env python3
"""Remove the known AnyKernel3 volume-key prompt, failing closed on drift."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FORBIDDEN = re.compile(
    r"keycheck\.timeout|handle_input|KEY_RESULT|KEY_VOLUME(?:UP|DOWN)?|"
    r"find_volume_nodes|VOLUME_DEVS|\bgetevent\b|/dev/input/event"
)
MAGISK_PROMPT = re.compile(
    r"(?ms)^if \[ -d /data/adb/magisk \] \|\| "
    r"\[ -f /sbin/\.magisk \]; then\n.*?^fi\n"
)
MODULES_DISABLED = re.compile(r"(?m)^[ \t]*do\.modules=0[ \t]*$")
SAFE_MAGISK_BLOCK = """if [ -d /data/adb/magisk ] || [ -f /sbin/.magisk ]; then
    ui_print "Magisk residual files detected"
    ui_print "Non-interactive default: No; nothing was flashed"
    ui_print "Remove Magisk residual files before flashing this kernel"
    exit 0
fi
"""
CORE_START = '\nKEY_RESULT=""\n'
CORE_END = "\n### end methods"


def shell_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.sh"):
        if path.is_symlink():
            raise SystemExit(f"refusing symbolic-link installer script: {path}")
        if path.is_file():
            files.append(path)

    update_binary = root / "META-INF" / "com" / "google" / "android" / "update-binary"
    if update_binary.exists() or update_binary.is_symlink():
        if update_binary.is_symlink() or not update_binary.is_file():
            raise SystemExit(f"refusing unsafe update-binary: {update_binary}")
        files.append(update_binary)
    return sorted(files)


def matches(root: Path) -> list[Path]:
    return [
        path
        for path in shell_files(root)
        if FORBIDDEN.search(path.read_text(encoding="utf-8"))
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ak3_root", type=Path)
    args = parser.parse_args()

    root = args.ak3_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"AnyKernel3 root is not a directory: {root}")
    entry = root / "anykernel.sh"
    core = root / "tools" / "ak3-core.sh"
    for path in (entry, core):
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"required AnyKernel3 script is missing or unsafe: {path}")

    found = matches(root)
    if not found:
        print("AnyKernel3 is already non-interactive")
        return 0

    entry_text = entry.read_text(encoding="utf-8")
    if len(MODULES_DISABLED.findall(entry_text)) != 1:
        raise SystemExit(
            "cannot safely default to No unless AnyKernel3 modules are disabled"
        )
    entry_text, property_count = re.subn(
        r"(?m)^[ \t]*keycheck\.timeout=.*\n",
        "",
        entry_text,
    )
    prompt_matches = list(MAGISK_PROMPT.finditer(entry_text))
    if len(prompt_matches) != 1:
        raise SystemExit(
            "unsupported AnyKernel3 prompt layout; refusing an unsafe rewrite "
            f"(matched {len(prompt_matches)} prompt blocks)"
        )
    prompt = prompt_matches[0]
    prompt_text = prompt.group(0)
    prompt_markers = ("handle_input", "KEY_RESULT", "KEY_VOLUMEUP", "KEY_VOLUMEDOWN")
    missing_prompt_markers = [
        marker for marker in prompt_markers if marker not in prompt_text
    ]
    if missing_prompt_markers:
        raise SystemExit(
            "unsupported AnyKernel3 prompt contents: "
            + ", ".join(missing_prompt_markers)
        )
    entry_text = entry_text[: prompt.start()] + SAFE_MAGISK_BLOCK + entry_text[prompt.end() :]
    if property_count != 1:
        raise SystemExit(
            f"expected one keycheck.timeout property, found {property_count}"
        )

    core_text = core.read_text(encoding="utf-8")
    start = core_text.find(CORE_START)
    end = core_text.find(CORE_END, start + len(CORE_START))
    if start < 0 or end < 0:
        raise SystemExit(
            "unsupported AnyKernel3 volume helper layout; refusing an unsafe rewrite"
        )
    helper_text = core_text[start:end]
    helper_markers = (
        "handle_input",
        "find_volume_nodes",
        "VOLUME_DEVS",
        "KEY_VOLUMEUP",
        "KEY_VOLUMEDOWN",
        "getevent",
        "/dev/input/event",
    )
    missing_helper_markers = [
        marker for marker in helper_markers if marker not in helper_text
    ]
    if missing_helper_markers:
        raise SystemExit(
            "unsupported AnyKernel3 volume helper contents: "
            + ", ".join(missing_helper_markers)
        )
    core_text = core_text[:start] + core_text[end:]

    replacements = {entry: entry_text, core: core_text}
    remaining = [
        path
        for path in shell_files(root)
        if FORBIDDEN.search(
            replacements.get(path, path.read_text(encoding="utf-8"))
        )
    ]
    if remaining:
        names = ", ".join(path.relative_to(root).as_posix() for path in remaining)
        raise SystemExit(f"volume-key interaction remains after sanitizing: {names}")

    required = (". tools/ak3-core.sh", "split_boot", "write_boot", "flash_boot")
    missing = [marker for marker in required if marker not in entry_text]
    if missing:
        raise SystemExit(
            "sanitizing damaged required flashing logic: " + ", ".join(missing)
        )

    # Do not modify either script until every upstream layout and safety check
    # above has succeeded.
    entry.write_text(entry_text, encoding="utf-8", newline="\n")
    core.write_text(core_text, encoding="utf-8", newline="\n")

    print("Removed AnyKernel3 volume-key prompt; non-interactive default is No")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
