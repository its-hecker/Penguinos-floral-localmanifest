#!/usr/bin/env python3
"""Guarded, idempotent addition of the Coral GUI shim step to prepare.py."""
from pathlib import Path
import sys

IMPORT_ANCHOR = "from qcom_namespace import fix_qcom_common_namespaces\n"
NEW_IMPORT = "from libgui_compat import fix_libgui_vendor_shims\n"
CALL_ANCHOR = "    if device == \"coral\":\n        fix_qcom_common_namespaces(Path.cwd())\n"
NEW_CALL = "        fix_libgui_vendor_shims(Path.cwd())\n"


def update_prepare(data: str) -> tuple[str, bool]:
    if NEW_IMPORT in data and NEW_CALL in data:
        return data, False
    if NEW_IMPORT in data or NEW_CALL in data:
        raise ValueError("Partial GUI compat hook found: refusing incomplete edit")
    if data.count(IMPORT_ANCHOR) != 1 or data.count(CALL_ANCHOR) != 1:
        raise ValueError("prepare.py changed upstream: expected anchors not unique")
    return (data.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + NEW_IMPORT, 1)
            .replace(CALL_ANCHOR, CALL_ANCHOR + NEW_CALL, 1), True)


def main():
    if len(sys.argv) != 2:
        print("Usage: inject_prepare.py <prepare.py>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        data, changed = update_prepare(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as err:
        print(err, file=sys.stderr)
        return 1
    if changed:
        path.write_text(data, encoding="utf-8")
    print("PenguinOS Coral GUI compatibility step:", "installed" if changed else "already present")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
