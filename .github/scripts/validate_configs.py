#!/usr/bin/env python3
"""Validate this fork's A14/A15/A16 configs and manifests."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REQUIRED_FIELDS = (
    "model",
    "soc",
    "branch",
    "manifest",
    "android_version",
    "kernel_version",
    "os_version",
)
LOCAL_POLICY = {"susfs": True, "kpm": True, "NMS": False, "bbg": False}
ALLOWED_AK3_SOURCES = {
    ("Bouteillepleine", "https://github.com/Bouteillepleine", "suite"),
    (
        "wild",
        "https://github.com/WildKernels",
        "287c4b33290704f558edbd169fa955fbe60bb6de",
    ),
}


def check_configs(root: Path, errors: list[str]) -> int:
    config_dirs = [root / "configs" / f"a{api}" for api in (14, 15, 16)]
    seen: dict[tuple[str, str], Path] = {}
    approved_paths: set[Path] = set()
    count = 0

    for config_dir in config_dirs:
        expected_os = f"A{config_dir.name[1:]}"
        manifest_dir = root / "manifests" / config_dir.name
        configs = sorted(config_dir.glob("*.json"))
        if not configs:
            errors.append(
                f"{config_dir.relative_to(root).as_posix()} has no JSON configurations"
            )

        for path in configs:
            approved_paths.add(path)
            count += 1
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                errors.append(f"{rel}: not a regular file")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{rel}: invalid JSON: {exc}")
                continue
            if not isinstance(data, dict):
                errors.append(f"{rel}: not a JSON object")
                continue

            for field in REQUIRED_FIELDS:
                value = data.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{rel}: {field} must be a non-empty string")
            if data.get("os_version") != expected_os:
                errors.append(f"{rel}: os_version must be {expected_os!r}")
            if data.get("model") != path.stem:
                errors.append(f"{rel}: model must be {path.stem!r}")

            identity = (str(data.get("os_version")), str(data.get("model")))
            if identity in seen:
                errors.append(
                    f"{rel}: duplicate os_version/model {identity!r}, already used by "
                    f"{seen[identity].relative_to(root).as_posix()}"
                )
            else:
                seen[identity] = path

            manifest = data.get("manifest")
            if (
                not isinstance(manifest, str)
                or not manifest.endswith(".xml")
                or Path(manifest).name != manifest
            ):
                errors.append(f"{rel}: manifest must be a local .xml filename")
            else:
                target = manifest_dir / manifest
                if target.is_symlink() or not target.is_file():
                    errors.append(
                        f"{rel}: missing manifest {target.relative_to(root).as_posix()}"
                    )

            for key, expected in LOCAL_POLICY.items():
                if data.get(key) is not expected:
                    errors.append(f"{rel}: {key} must be {expected!r}")

    for path in sorted((root / "configs").rglob("*.json")):
        if path not in approved_paths:
            errors.append(
                f"{path.relative_to(root).as_posix()}: outside the supported "
                "top-level A14/A15/A16 inventory"
            )

    return count


def check_manifests(root: Path, errors: list[str]) -> int:
    paths = sorted((root / "manifests").glob("a1[456]/*.xml"))
    if not paths:
        errors.append("manifests/ contains no A14/A15/A16 XML manifests")

    for path in paths:
        rel = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            errors.append(f"{rel}: not a regular file")
            continue
        try:
            document = ET.parse(path)
        except Exception as exc:
            errors.append(f"{rel}: invalid XML: {exc}")
            continue
        if document.getroot().tag != "manifest":
            errors.append(f"{rel}: XML root must be <manifest>")
            continue

        remotes = {
            remote.get("name") or "": (remote.get("fetch") or "").rstrip("/")
            for remote in document.getroot().iter("remote")
        }
        ak3_sources = {
            (
                project.get("remote") or "",
                remotes.get(project.get("remote") or "", ""),
                project.get("revision") or "",
            )
            for project in document.getroot().iter("project")
            if project.get("name") == "AnyKernel3"
        }
        if len(ak3_sources) != 1:
            errors.append(f"{rel}: expected exactly one AnyKernel3 source")
        elif not ak3_sources.issubset(ALLOWED_AK3_SOURCES):
            errors.append(
                f"{rel}: unapproved AnyKernel3 source {next(iter(ak3_sources))!r}"
            )

    return len(paths)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors: list[str] = []
    config_count = check_configs(root, errors)
    manifest_count = check_manifests(root, errors)

    if errors:
        for error in errors:
            print(f"::error::{error}")
        print(f"{len(errors)} problem(s) found", file=sys.stderr)
        return 1

    print(f"validated {config_count} configurations and {manifest_count} manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
