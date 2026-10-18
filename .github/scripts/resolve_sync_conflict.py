#!/usr/bin/env python3
"""Resolve selected text conflicts while preserving reviewed fork behavior."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ALLOWED_PATHS = {
    ".github/workflows/build-kernel-release.yml",
    "README.md",
}
ALLOWED_PATTERNS = (
    re.compile(r"manifests/a(?:14|15|16)/[^/]+\.xml"),
)
START = "<<<<<<< "
BASE = "||||||| "
MIDDLE = "======="
END = ">>>>>>> "


def resolve_text(text: str, name: str) -> tuple[str, int, int]:
    output: list[str] = []
    ours: list[str] = []
    base: list[str] = []
    theirs: list[str] = []
    state = "normal"
    conflict_count = 0
    upstream_additions = 0

    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        if state == "normal":
            if line.startswith(START):
                state = "ours"
                ours = []
                base = []
                theirs = []
            elif line.startswith((BASE, MIDDLE, END)):
                raise ValueError(f"{name}:{line_number}: unexpected conflict marker")
            else:
                output.append(line)
        elif state == "ours":
            if line.startswith(BASE):
                state = "base"
            elif line.startswith((START, MIDDLE, END)):
                raise ValueError(f"{name}:{line_number}: malformed conflict")
            else:
                ours.append(line)
        elif state == "base":
            if line.startswith(MIDDLE):
                state = "theirs"
            elif line.startswith((START, BASE, END)):
                raise ValueError(f"{name}:{line_number}: malformed conflict")
            else:
                base.append(line)
        else:
            if line.startswith(END):
                # A diff3 base distinguishes a genuine upstream-only addition
                # from a local deletion that upstream modified.  Keep the latter.
                if (
                    not "".join(ours).strip()
                    and not "".join(base).strip()
                    and "".join(theirs).strip()
                ):
                    output.extend(theirs)
                    upstream_additions += 1
                else:
                    output.extend(ours)
                conflict_count += 1
                state = "normal"
            elif line.startswith((START, BASE, MIDDLE)):
                raise ValueError(f"{name}:{line_number}: malformed conflict")
            else:
                theirs.append(line)

    if state != "normal":
        raise ValueError(f"{name}: unterminated conflict")
    if conflict_count == 0:
        raise ValueError(f"{name}: no conflict markers found")

    resolved = "".join(output)
    for line in resolved.splitlines():
        if line.startswith((START, BASE, MIDDLE, END)):
            raise ValueError(f"{name}: conflict marker remains after resolution")
    return resolved, conflict_count, upstream_additions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    root = args.root.resolve()
    pending: list[tuple[Path, str, int, int]] = []
    for raw_path in args.paths:
        rel = Path(raw_path).as_posix()
        if rel not in ALLOWED_PATHS and not any(
            pattern.fullmatch(rel) for pattern in ALLOWED_PATTERNS
        ):
            raise SystemExit(f"refusing unapproved conflict path: {rel}")
        path = root / rel
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"conflicted path is missing or unsafe: {rel}")
        try:
            resolved, count, additions = resolve_text(
                path.read_text(encoding="utf-8"), rel
            )
        except (UnicodeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        pending.append((path, resolved, count, additions))

    # Validate every requested file before changing any of them.
    for path, resolved, count, additions in pending:
        path.write_text(resolved, encoding="utf-8", newline="\n")
        print(
            f"resolved {path.relative_to(root).as_posix()}: "
            f"{count} conflict(s), accepted {additions} upstream-only addition(s)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
