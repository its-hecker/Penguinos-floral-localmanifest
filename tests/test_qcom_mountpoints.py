#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for Qualcomm/Soong directory-rule coexistence."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from qcom_mountpoints import (
    QCOM_BOARD, SOONG_MKDIR, RECIPE,
    fix_qcom_mountpoint_rules, qualcomm_targets, transform,
)

QCOM = """FIRMWARE_MOUNT_POINT := $(TARGET_OUT_VENDOR)/firmware_mnt
BT_FIRMWARE_MOUNT_POINT := $(TARGET_OUT_VENDOR)/bt_firmware
DSP_MOUNT_POINT := $(TARGET_OUT_VENDOR)/dsp
SOCCP_MOUNT_POINT := $(TARGET_OUT_VENDOR)/soccp_firmware
VM_MOUNT_POINT := $(TARGET_OUT_PRODUCT)/vm-system
PERSIST_MOUNT_POINT := $(TARGET_ROOT_OUT)/persist
$(FIRMWARE_MOUNT_POINT):
\t@mkdir -p $@
$(BT_FIRMWARE_MOUNT_POINT):
\t@mkdir -p $@
$(DSP_MOUNT_POINT):
\t@mkdir -p $@
$(SOCCP_MOUNT_POINT):
\t@mkdir -p $@
$(VM_MOUNT_POINT):
\t@mkdir -p $@
$(PERSIST_MOUNT_POINT):
\t@ln -sf something elsewhere
"""
MKDIR = "include $(BUILD_SYSTEM)/base_rules.mk\n\n" + RECIPE + "\nMORE := value\n"
LEGACY = (
    "ifeq ($(and $(filter coral flame,$(TARGET_DEVICE)),"
    "$(filter $(LOCAL_SOONG_INSTALL_DIR),$(TARGET_OUT_VENDOR)/firmware_mnt "
    "$(TARGET_OUT_VENDOR)/bt_firmware $(TARGET_OUT_VENDOR)/dsp)),)\n"
    + RECIPE + "endif\n"
)


class MountpointRulesTest(unittest.TestCase):
    def test_discovers_vendor_product_and_root_mounts(self):
        names = qualcomm_targets(QCOM)
        self.assertEqual(names, {
            "$(TARGET_OUT_VENDOR)/firmware_mnt",
            "$(TARGET_OUT_VENDOR)/bt_firmware",
            "$(TARGET_OUT_VENDOR)/dsp",
            "$(TARGET_OUT_VENDOR)/soccp_firmware",
            "$(TARGET_OUT_PRODUCT)/vm-system",
            "$(TARGET_ROOT_OUT)/persist",
        })

    def test_updates_pristine_rule_and_is_idempotent(self):
        fixed = transform(MKDIR, qualcomm_targets(QCOM))
        self.assertIn("$(TARGET_OUT_VENDOR)/soccp_firmware", fixed)
        self.assertIn("$(TARGET_OUT_VENDOR)/firmware_mnt", fixed)
        self.assertIn("$(TARGET_ROOT_OUT)/persist", fixed)
        self.assertIn("$(filter coral flame,$(TARGET_DEVICE))", fixed)
        self.assertEqual(fixed.count(RECIPE), 1)
        self.assertEqual(fixed, transform(fixed, qualcomm_targets(QCOM)))
        self.assertTrue(fixed.endswith("MORE := value\n"))

    def test_replaces_previous_local_only_three_mount_fix(self):
        fixed = transform(MKDIR.replace(RECIPE, LEGACY), qualcomm_targets(QCOM))
        self.assertEqual(fixed.count(RECIPE), 1)
        self.assertIn("$(TARGET_OUT_VENDOR)/soccp_firmware", fixed)
        self.assertIn("$(TARGET_ROOT_OUT)/persist", fixed)
        self.assertEqual(fixed, transform(fixed, qualcomm_targets(QCOM)))

    def test_upgrades_existing_vendor_only_compatibility(self):
        first = transform(MKDIR, {
            "$(TARGET_OUT_VENDOR)/firmware_mnt",
            "$(TARGET_OUT_VENDOR)/soccp_firmware",
        })
        fixed = transform(first, qualcomm_targets(QCOM))
        self.assertIn("$(TARGET_ROOT_OUT)/persist", fixed)
        self.assertEqual(fixed.count(RECIPE), 1)
        self.assertEqual(fixed, transform(fixed, qualcomm_targets(QCOM)))

    def test_fails_closed_when_upstream_rule_is_unexpected(self):
        with self.assertRaises(ValueError):
            transform("unexpected target:\n\t@echo nope\n", qualcomm_targets(QCOM))
        with self.assertRaises(ValueError):
            transform(MKDIR, set())

    def test_full_prepare_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            board = base / QCOM_BOARD
            mkdir = base / SOONG_MKDIR
            board.parent.mkdir(parents=True)
            mkdir.parent.mkdir(parents=True)
            board.write_text(QCOM)
            mkdir.write_text(MKDIR)
            self.assertEqual(fix_qcom_mountpoint_rules(base), [mkdir])
            self.assertEqual(fix_qcom_mountpoint_rules(base), [])
            self.assertIn("soccp_firmware", mkdir.read_text())
            self.assertIn("$(TARGET_ROOT_OUT)/persist", mkdir.read_text())


if __name__ == "__main__":
    unittest.main()
