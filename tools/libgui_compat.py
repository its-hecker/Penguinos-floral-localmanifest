#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Coral only: map obsolete LineageOS libgui_vendor shim dependencies to libgui.

PenguinOS Celerity frameworks/native/libs/gui/Android.bp defines a vendor-
available libgui shared library but does not define libgui_vendor. This helper
only updates the two vendor compatibility shims after other patches are applied.
"""
from pathlib import Path
import re

SHIMS = ("libgui_shim_vendor", "libgui_buffer_shim_vendor")
SOURCE = Path("hardware/lineage/compat/Android.bp")
PROVIDER = Path("frameworks/native/libs/gui/Android.bp")


def named_module_block(source: str, module_type: str, name: str) -> re.Match:
    expression = (
        r"(?m)^" + re.escape(module_type) + r'\s*\{\s*\n\s*name:\s*"' +
        re.escape(name) + r'",(?:(?!^\}).)*^\}'
    )
    matches = list(re.finditer(expression, source, flags=re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {module_type} definition for {name}, got {len(matches)}")
    return matches[0]


def provider_supports_vendor(source: str) -> bool:
    provider = named_module_block(source, "cc_library_shared", "libgui").group(0)
    return bool(re.search(r"\bvendor_available\s*:\s*true\b", provider))


def update_shim_dependencies(source: str) -> tuple[str, list[str]]:
    updated = source
    changes = []
    for name in SHIMS:
        # libgui_shim_vendor is a cc_library; the buffer shim is cc_library_shared.
        module_type = "cc_library_shared" if name == "libgui_buffer_shim_vendor" else "cc_library"
        match = named_module_block(updated, module_type, name)
        block = match.group(0)
        libraries = list(re.finditer(r"\bshared_libs\s*:\s*\[(.*?)\]", block, re.DOTALL))
        if len(libraries) != 1:
            raise ValueError(f"{name}: expected one shared_libs list")
        libmatch = libraries[0]
        liblist = libmatch.group(1)
        before = liblist.count('"libgui_vendor"')
        after = liblist.count('"libgui"')
        if (before, after) == (0, 1):
            continue  # already patched
        if (before, after) != (1, 0):
            raise ValueError(f"{name}: unsupported GUI library dependency layout")
        newliblist = liblist.replace('"libgui_vendor"', '"libgui"', 1)
        modified = block[:libmatch.start(1)] + newliblist + block[libmatch.end(1):]
        updated = updated[:match.start()] + modified + updated[match.end():]
        changes.append(name)
    return updated, changes


def fix_libgui_vendor_shims(root: Path) -> list[str]:
    root = Path(root)
    compat = root / SOURCE
    provider_path = root / PROVIDER
    if not compat.is_file() or not provider_path.is_file():
        raise FileNotFoundError("Coral compatibility or PenguinOS frameworks/native libgui Android.bp is missing")
    if not provider_supports_vendor(provider_path.read_text(encoding="utf-8")):
        raise ValueError("PenguinOS libgui no longer exports a vendor variant: refusing unsafe substitution")
    original = compat.read_text(encoding="utf-8")
    updated, changes = update_shim_dependencies(original)
    if changes:
        compat.write_text(updated, encoding="utf-8")
        print("PenguinOS Coral: linked vendor GUI shims against libgui:", ", ".join(changes))
    else:
        print("PenguinOS Coral: vendor GUI shims already use libgui")
    return changes
