#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Restore Qualcomm vendor Soong namespace visibility for PenguinOS Coral.

Some legacy Qualcomm prebuilt modules in vendor/qcom/common have explicit
namespaces.  The LineageOS SM8150 implementations of their dependencies are
also explicitly namespaced; the legacy imports must refer to those namespaces.

Apply only the namespace declarations confirmed by Coral build logs.
Run from the ROM source root, via tools/prepare.py. Safe to rerun.
"""

from pathlib import Path
import re


TARGETS = (
    *(
        (Path(f"vendor/qcom/common/vendor/display/{version}/Android.bp"),
         "hardware/qcom/sm8150/display", "libdisplaydebug")
        for version in ("4.14", "4.19", "5.4", "5.10", "5.15")
    ),
    (Path("vendor/qcom/common/vendor/gps-legacy/Android.bp"),
     "hardware/qcom/sm8150/gps", "libgps.utils"),
    (Path("vendor/qcom/common/vendor/wlan/Android.bp"),
     "hardware/qcom/wlan/legacy", "libcld80211"),
    (Path("vendor/qcom/common/vendor/wlan-legacy/Android.bp"),
     "hardware/qcom/wlan/legacy", "libcld80211"),
    (Path("vendor/qcom/common/vendor/qseecomd-legacy/Android.bp"),
     "vendor/qcom/opensource/display", "libdisplayconfig.qti"),
    (Path("vendor/qcom/common/vendor/qseecomd/Android.bp"),
     "vendor/qcom/opensource/display", "libdisplayconfig.qti"),
    (Path("vendor/qcom/common/vendor/display/5.15/Android.bp"),
     "vendor/qcom/common/vendor/display/4.14", "libsdedrm"),
)

# Soong namespaces are defined by their containing directory. A plain
# PRODUCT_SOONG_NAMESPACES change would not repair module-to-module imports.
NAMESPACE = re.compile(r"(?m)^[ \t]*soong_namespace[ \t]*\{")
IMPORTS = re.compile(r"\bimports\s*:\s*\[")


def add_import(text: str, namespace: str, module_name: str) -> tuple[str, bool]:
    """Add an import without dropping existing namespace imports or properties."""
    if not re.search(r'"' + re.escape(module_name) + r'"', text):
        raise ValueError(f"Expected reference to {module_name!r} is missing")

    match = NAMESPACE.search(text)
    if match is None:
        raise ValueError("Missing explicit soong_namespace declaration")

    opening_brace = text.find("{", match.start(), match.end())
    closing_brace = text.find("}", opening_brace + 1)
    if closing_brace == -1:
        raise ValueError("Unterminated soong_namespace declaration")

    body = text[opening_brace + 1:closing_brace]
    present = re.search(r'"' + re.escape(namespace) + r'"', body)
    if present:
        return text, False

    imports = IMPORTS.search(body)
    if imports is not None:
        # Insert at the start of the imports list; existing entries and
        # their trailing comments remain unchanged, including one-line lists.
        at = opening_brace + 1 + imports.end()
        return text[:at] + f'\n        "{namespace}",' + text[at:], True

    # A declaration with no imports, commonly 'soong_namespace {}'.
    insertion = f'\n    imports: [\n        "{namespace}",\n    ],\n'
    at = opening_brace + 1
    return text[:at] + insertion + text[at:], True


def fix_qcom_common_namespaces(root: Path) -> list[Path]:
    """Validate all imports first; then update each unique Android.bp once.

    The 5.15 display Android.bp needs both libdisplaydebug and libsdedrm,
    so we must apply edits to the staged text instead of re-reading the file.
    """
    root = Path(root)
    originals: dict[Path, str] = {}
    staged: dict[Path, str] = {}
    for relative, target_namespace, module in TARGETS:
        destination = root / relative
        if destination not in originals:
            if not destination.is_file():
                raise FileNotFoundError(
                    f"{destination}: required PenguinOS vendor/qcom/common Android.bp "
                    "not present. Ensure repo sync finished successfully."
                )
            originals[destination] = destination.read_text(encoding="utf-8")
            staged[destination] = originals[destination]
        try:
            updated, _ = add_import(staged[destination], target_namespace, module)
        except ValueError as exc:
            raise ValueError(f"{destination}: {exc}") from exc
        staged[destination] = updated

    # No writes unless EVERY dependency was validated. Write a file only once.
    changed_paths = [p for p in staged if staged[p] != originals[p]]
    for path in changed_paths:
        path.write_text(staged[path], encoding="utf-8")
        print(f"PenguinOS Coral Soong namespace: imported dependency in {path}")
    if not changed_paths:
        print("PenguinOS Coral Soong namespaces: already configured")
    return changed_paths
