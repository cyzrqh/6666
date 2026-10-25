"""Keep the Oplus NFC helper within its real project-service link dependency."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


NFC = Path("drivers/nfc/oplus_nfc/Kconfig")
SOURCE = NFC.with_name("oplus_nfc.c")
PROVIDER = Path("drivers/soc/oplus/boot/oplus_project/Kconfig")
DEPENDENCY = "depends on OPLUS_FEATURE_OPROJECT"


def repair(tree: Path) -> bool:
    path = tree / NFC
    if not path.is_file():
        return False
    source = (tree / SOURCE).read_text(encoding="utf-8")
    if not all(re.search(rf"\b{name}\s*\(", source) for name in (
        "get_project", "get_Operator_Version"
    )):
        raise ValueError("Unrecognized Oplus NFC project-service calls")
    provider = (tree / PROVIDER).read_text(encoding="utf-8")
    if not re.search(r"(?m)^\s*config OPLUS_FEATURE_OPROJECT\s*$", provider):
        raise ValueError("The Oplus project-service Kconfig symbol is missing")

    contents = path.read_bytes().decode("utf-8")
    lines = contents.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == "config OPLUS_NFC"]
    if len(starts) != 1:
        raise ValueError("Expected exactly one OPLUS_NFC Kconfig entry")
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if re.match(
        r"\s*(?:config|menuconfig|endmenu|endif|endchoice)\b", lines[i]
    )), len(lines))
    if any(line.strip() == DEPENDENCY for line in lines[start + 1:end]):
        return False
    types = [i for i in range(start + 1, end) if re.match(r'\s*tristate\s+"', lines[i])]
    if len(types) != 1:
        raise ValueError("Expected a tristate OPLUS_NFC entry")
    position = types[0]
    indent = re.match(r"\s*", lines[position]).group(0)
    newline = "\r\n" if lines[position].endswith("\r\n") else "\n"
    lines.insert(position + 1, indent + DEPENDENCY + newline)
    path.write_bytes("".join(lines).encode("utf-8"))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    changed = repair(args.tree)
    print("Oplus NFC project-service dependency " + ("added" if changed else "unchanged"))


if __name__ == "__main__":
    main()
