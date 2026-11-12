#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for PenguinOS Coral Lineage Health sysfs policy compatibility."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/aospa-floral-health-sysfs-types.patch"
HEALTH = """type hal_lineage_health_default, domain;
hal_server_domain(hal_lineage_health_default, hal_lineage_health)

type hal_lineage_health_default_exec, exec_type, vendor_file_type, file_type;
init_daemon_domain(hal_lineage_health_default)

binder_call(hal_lineage_health_default, servicemanager);

# Allow LineageHealth HAL to write to battery and usb sysfs node
allow hal_lineage_health_default vendor_sysfs_battery_supply:dir search;
allow hal_lineage_health_default vendor_sysfs_battery_supply:file rw_file_perms;
allow hal_lineage_health_default vendor_sysfs_usb_supply:dir search;
allow hal_lineage_health_default vendor_sysfs_usb_supply:file rw_file_perms;
"""
POWER_INSIGHT = """# PowerInsight
allow system_server vendor_sysfs_battery_supply:dir r_dir_perms;
allow system_server vendor_sysfs_battery_supply:file r_file_perms;
"""


class FloralHealthPolicyTest(unittest.TestCase):
    def test_pinned_aospa_health_policy_patch_is_reversible(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            health = root / "sepolicy/vendor/hal_lineage_health_default.te"
            power = root / "sepolicy/qcom/dynamic/system_server.te"
            for file, source in ((health, HEALTH), (power, POWER_INSIGHT)):
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(source)

            subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=root, check=True)
            subprocess.run(["git", "apply", str(PATCH)], cwd=root, check=True)
            result = health.read_text()
            self.assertNotIn("vendor_sysfs_battery_supply", result)
            self.assertNotIn("vendor_sysfs_usb_supply", result)
            self.assertIn("sysfs_battery_supply:dir search;", result)
            self.assertIn("sysfs_battery_supply:file rw_file_perms;", result)
            self.assertIn("sysfs_usb_supply:dir search;", result)
            self.assertIn("sysfs_usb_supply:file rw_file_perms;", result)
            self.assertIn("sysfs_battery_supply:file r_file_perms;", power.read_text())
            subprocess.run(["git", "apply", "--reverse", "--check", str(PATCH)],
                           cwd=root, check=True)

    def test_device_defines_selected_vendor_sysfs_types(self):
        device_type_file = Path("device/google/coral/sepolicy/vendor/qcom/common/file.te")
        if not device_type_file.exists():
            self.skipTest("Run from the fully synced PenguinOS Floral source root")
        definitions = device_type_file.read_text()
        self.assertIn("type sysfs_battery_supply, sysfs_type, fs_type;", definitions)
        self.assertIn("type sysfs_usb_supply, sysfs_type, fs_type;", definitions)

    def test_coral_preparation_applies_patch(self):
        script = (ROOT / "tools/prepare.py").read_text()
        self.assertIn('PATCHES / "aospa-floral-health-sysfs-types.patch"', script)
        self.assertIn('if device == "coral":', script)


if __name__ == "__main__":
    unittest.main()
