#!/usr/bin/env python3
"""Apply the fork's required kernel defaults after an upstream merge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


POLICY = {
    "susfs": True,
    "kpm": True,
    "NMS": False,
    "bbg": False,
}
def normalized_config(
    path: Path,
    data: dict[str, object],
) -> dict[str, object]:
    result: dict[str, object] = {}
    missing_policy = POLICY.keys() - data.keys()

    for key, value in data.items():
        if key == "model":
            result[key] = path.stem
        elif key in POLICY:
            result[key] = POLICY[key]
        else:
            result[key] = value
        if key == "hmbird":
            for policy_key in POLICY:
                if policy_key in missing_policy:
                    result[policy_key] = POLICY[policy_key]

    for policy_key in POLICY:
        if policy_key not in result:
            result[policy_key] = POLICY[policy_key]

    if "model" not in result:
        result["model"] = path.stem

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="report policy violations without changing files",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (defaults to the script's repository)",
    )
    args = parser.parse_args()

    repo_root = args.root.resolve()
    config_root = repo_root / "configs"

    paths = sorted(config_root.glob("a1[456]/*.json"))
    if not paths:
        raise SystemExit("no A14/A15/A16 configuration files found")

    changed: list[Path] = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"refusing non-regular configuration: {path}")

        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
        if not isinstance(data, dict):
            raise SystemExit(f"configuration must contain a JSON object: {path}")

        normalized = normalized_config(path, data)
        semantic_change = normalized != data
        rendered = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
        if semantic_change:
            changed.append(path.relative_to(repo_root))
            if not args.check:
                path.write_text(rendered, encoding="utf-8", newline="\n")

    if changed:
        verb = "violates" if args.check else "updated"
        for path in changed:
            print(f"{verb}: {path.as_posix()}")
        if args.check:
            return 1

    print(f"local policy verified for {len(paths)} configurations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
