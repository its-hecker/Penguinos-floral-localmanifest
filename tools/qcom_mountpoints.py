#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Keep Qualcomm mountpoint recipes from conflicting with Soong mkdir."""

from pathlib import Path
import re

QCOM_BOARD = Path("vendor/qcom/opensource/core-utils/build/AndroidBoardCommon.mk")
SOONG_MKDIR = Path("vendor/aospa/build/core/mkdir.mk")
RECIPE = "$(LOCAL_SOONG_INSTALL_DIR):\n\t@mkdir -p $@\n"
START = "# BEGIN PenguinOS Floral Qualcomm mountpoint compatibility\n"
END = "# END PenguinOS Floral Qualcomm mountpoint compatibility\n"
LEGACY = "ifeq ($(and $(filter coral flame,$(TARGET_DEVICE)),"
LEGACY_COMMENT = "# PenguinOS Floral: Qualcomm's AndroidBoardCommon.mk owns these mountpoints.\n"

ASSIGNMENT = re.compile(
    r"(?m)^[ \t]*([A-Za-z_]\w*)[ \t]*[:?+]?=[ \t]*"
    r"\$\((TARGET_OUT_VENDOR|TARGET_OUT_PRODUCT)\)/([\w./-]+)"
)
VARIABLE_RULE = re.compile(r"(?m)^[ \t]*\$\(([A-Za-z_]\w*)\)[ \t]*:(?![=])")
DIRECT_RULE = re.compile(
    r"(?m)^[ \t]*\$\((TARGET_OUT_VENDOR|TARGET_OUT_PRODUCT)\)"
    r"/([\w./-]+)[ \t]*:(?![=])"
)


def qualcomm_targets(contents: str) -> set[str]:
    """Find targets owned by rules in the synced Qualcomm board makefile."""
    variables = {
        variable: f"$({root})/{name}"
        for variable, root, name in ASSIGNMENT.findall(contents)
    }
    paths = {
        variables[variable]
        for variable in VARIABLE_RULE.findall(contents)
        if variable in variables
    }
    paths.update(f"$({root})/{name}" for root, name in DIRECT_RULE.findall(contents))
    return paths


def transform(contents: str, targets: set[str]) -> str:
    if not targets:
        raise ValueError("No Qualcomm mountpoint rules found; refusing to change mkdir.mk")
    block = (
        START +
        "ifeq ($(and $(filter coral flame,$(TARGET_DEVICE)),"
        "$(filter $(LOCAL_SOONG_INSTALL_DIR)," + " ".join(sorted(targets)) + ")),)\n"
        + RECIPE + "endif\n" + END
    )
    if START in contents:
        begin = contents.index(START)
        if contents.count(START) != 1 or contents.count(END) != 1:
            raise ValueError("Ambiguous existing Qualcomm compatibility block")
        finish = contents.index(END, begin) + len(END)
    elif LEGACY in contents:
        begin = contents.index(LEGACY)
        finish = contents.index("endif\n", begin) + len("endif\n")
        if contents[:begin].endswith(LEGACY_COMMENT):
            begin -= len(LEGACY_COMMENT)
    else:
        if contents.count(RECIPE) != 1:
            raise ValueError("Expected Soong mkdir recipe not found exactly once")
        begin = contents.index(RECIPE)
        finish = begin + len(RECIPE)
    if contents[begin:finish].count(RECIPE) != 1:
        raise ValueError("Existing mkdir block differs; refusing to overwrite")
    return contents[:begin] + block + contents[finish:]


def fix_qcom_mountpoint_rules(root: Path) -> list[Path]:
    root = Path(root)
    board = root / QCOM_BOARD
    mkdir = root / SOONG_MKDIR
    if not board.is_file() or not mkdir.is_file():
        raise FileNotFoundError("Sync Qualcomm core-utils and vendor/aospa before preparing Floral")
    targets = qualcomm_targets(board.read_text(encoding="utf-8"))
    original = mkdir.read_text(encoding="utf-8")
    modified = transform(original, targets)
    if modified == original:
        print("PenguinOS Floral: Qualcomm mountpoint compatibility already configured")
        return []
    mkdir.write_text(modified, encoding="utf-8")
    print("PenguinOS Floral: excluded duplicate Soong mkdir recipes for " + ", ".join(sorted(targets)))
    return [mkdir]
