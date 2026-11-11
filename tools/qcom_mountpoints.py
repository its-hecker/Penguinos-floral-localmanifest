#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Keep Qualcomm mountpoint and root symlink recipes from conflicting with Soong mkdir."""

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
    r"\$\((TARGET_OUT_VENDOR|TARGET_OUT_PRODUCT|TARGET_ROOT_OUT)\)/([\w./-]+)"
)
VARIABLE_RULE = re.compile(r"(?m)^[ \t]*\$\(([A-Za-z_]\w*)\)[ \t]*:(?![=])")
DIRECT_RULE = re.compile(
    r"(?m)^[ \t]*\$\((TARGET_OUT_VENDOR|TARGET_OUT_PRODUCT|TARGET_ROOT_OUT)\)"
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


PERSIST_GUARD_START = "# BEGIN PenguinOS Floral root persist symlink ownership\n"
PERSIST_GUARD_END = "# END PenguinOS Floral root persist symlink ownership\n"
PERSIST_RULE = "$(PERSIST_MOUNT_POINT):\n"


def guard_root_persist_rule(contents: str) -> str:
    """Give the rootdir BOARD_ROOT_EXTRA_SYMLINKS rule sole ownership of /persist.

    Qualcomm's own root/persist rule conflicts with create_root_structure.mk
    when the device already has /mnt/vendor/persist:/persist as a root symlink.
    Keep Qualcomm's original rule for configurations without that symlink.
    """
    if PERSIST_GUARD_START in contents or PERSIST_GUARD_END in contents:
        if contents.count(PERSIST_GUARD_START) != 1 or contents.count(PERSIST_GUARD_END) != 1:
            raise ValueError("Malformed Qualcomm persist guard")
        start = contents.index(PERSIST_GUARD_START)
        finish = contents.index(PERSIST_GUARD_END, start)
        current = contents[start:finish]
        if PERSIST_RULE not in current or "BOARD_ROOT_EXTRA_SYMLINKS" not in current:
            raise ValueError("Unexpected Qualcomm persist guard contents")
        return contents
    if contents.count(PERSIST_RULE) != 1:
        raise ValueError("Expected exactly one Qualcomm PERSIST_MOUNT_POINT rule")
    if "PERSIST_MOUNT_POINT := $(TARGET_ROOT_OUT)/persist" not in contents:
        raise ValueError("Unexpected Qualcomm persist output location")
    start = contents.index(PERSIST_RULE)
    finish = contents.find("\nendif\n", start)
    if finish < 0:
        raise ValueError("Qualcomm persist rule has no terminating conditional")
    finish += len("\nendif\n")
    original_rule = contents[start:finish]
    if (
        '@echo "Creating $(PERSIST_MOUNT_POINT)"' not in original_rule
        or "ifneq ($(TARGET_MOUNT_POINTS_SYMLINKS),false)" not in original_rule
        or "@ln -sf /mnt/vendor/persist $(TARGET_ROOT_OUT)/persist" not in original_rule
    ):
        raise ValueError("Unexpected Qualcomm persist recipe; refusing to change it")
    guard = (
        PERSIST_GUARD_START
        + "ifeq ($(filter /mnt/vendor/persist:/persist,$(BOARD_ROOT_EXTRA_SYMLINKS)),)\n"
        + original_rule
        + "endif\n"
        + PERSIST_GUARD_END
    )
    return contents[:start] + guard + contents[finish:]


def fix_qcom_mountpoint_rules(root: Path) -> list[Path]:
    root = Path(root)
    board = root / QCOM_BOARD
    mkdir = root / SOONG_MKDIR
    if not board.is_file() or not mkdir.is_file():
        raise FileNotFoundError("Sync Qualcomm core-utils and vendor/aospa before preparing Floral")
    board_config = root / "device/google/coral/BoardConfig-common.mk"
    rootdir = root / "system/core/rootdir/create_root_structure.mk"
    if not board_config.is_file() or not rootdir.is_file():
        raise FileNotFoundError("Floral board config or rootdir source missing")
    if "/mnt/vendor/persist:/persist" not in board_config.read_text(encoding="utf-8"):
        raise ValueError("Floral no longer declares its root persist symlink")
    rootdir_content = rootdir.read_text(encoding="utf-8")
    if "ALL_ROOTDIR_SYMLINKS += $(foreach s,$(BOARD_ROOT_EXTRA_SYMLINKS)" not in rootdir_content:
        raise ValueError("PenguinOS rootdir no longer owns BOARD_ROOT_EXTRA_SYMLINKS")

    board_original = board.read_text(encoding="utf-8")
    board_modified = guard_root_persist_rule(board_original)
    targets = qualcomm_targets(board_modified)
    original = mkdir.read_text(encoding="utf-8")
    modified = transform(original, targets)

    changed = []
    if board_modified != board_original:
        board.write_text(board_modified, encoding="utf-8")
        changed.append(board)
        print("PenguinOS Floral: rootdir now solely owns the /persist symlink")
    if modified != original:
        mkdir.write_text(modified, encoding="utf-8")
        changed.append(mkdir)
        print("PenguinOS Floral: excluded duplicate Soong mkdir recipes for " + ", ".join(sorted(targets)))
    if not changed:
        print("PenguinOS Floral: Qualcomm mountpoint compatibility already configured")
    return changed
