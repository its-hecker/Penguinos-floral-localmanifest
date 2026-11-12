#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Coral/Flame Pixel Touch HAL SELinux regression checks."""

from pathlib import Path
import re
import unittest

ROOT = Path("device/google/coral")
POLICY = ROOT / "sepolicy"
ATTRIBUTES = POLICY / "system_ext/public/attributes"
TOUCH = POLICY / "vendor/lineage/hal_lineage_touch_default.te"
SERVICES = POLICY / "vendor/lineage/service_contexts"
SEPOLICY_MK = POLICY / "coral-sepolicy.mk"
PIXEL_TOUCH = Path("hardware/google/pixel/touch/device.mk")
PIXEL_SEPOLICY = Path("hardware/google/pixel-sepolicy/touch")
INTERFACES = (
    "IGloveMode", "IHighTouchPollingRate", "IKeyDisabler",
    "IKeySwapper", "IStylusMode", "ITouchscreenGesture",
)


class PixelTouchPolicyTest(unittest.TestCase):
    def setUp(self):
        self.attrs = ATTRIBUTES.read_text()
        self.touch = TOUCH.read_text()
        self.contexts = SERVICES.read_text()
        self.mk = SEPOLICY_MK.read_text()

    def test_public_hal_attributes_defined(self):
        self.assertEqual(
            self.attrs.count("hal_attribute(lineage_touch)"), 1
        )
        self.assertIn("hal_attribute(lineage_livedisplay)", self.attrs)
        self.assertIn(
            "SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS += device/google/coral/sepolicy/system_ext/public",
            self.mk
        )

    def test_vendor_hal_domain_and_service_permissions(self):
        expected = (
            "type hal_lineage_touch_default, domain;",
            "hal_server_domain(hal_lineage_touch_default, hal_lineage_touch)",
            "type hal_lineage_touch_default_exec, exec_type, vendor_file_type, file_type;",
            "init_daemon_domain(hal_lineage_touch_default)",
            "type hal_lineage_touch_service, hal_service_type, service_manager_type;",
            "binder_call(hal_lineage_touch_client, hal_lineage_touch_server)",
            "hal_attribute_service(hal_lineage_touch, hal_lineage_touch_service)",
        )
        for declaration in expected:
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, self.touch)
        self.assertIn(
            "BOARD_VENDOR_SEPOLICY_DIRS += device/google/coral/sepolicy/vendor/lineage",
            self.mk
        )
        self.assertNotIn("permissive hal_lineage_touch_default", self.touch)

    def test_service_contexts_match_lineage(self):
        for interface in INTERFACES:
            entry = f"vendor.lineage.touch.{interface}/default"
            matches = [
                line for line in self.contexts.splitlines()
                if line.split()[:1] == [entry]
            ]
            self.assertEqual(len(matches), 1, entry)
            self.assertEqual(
                matches[0].split()[1],
                "u:object_r:hal_lineage_touch_service:s0",
            )

    def test_pixel_touch_hal_package_and_file_label(self):
        if not PIXEL_TOUCH.exists() or not PIXEL_SEPOLICY.exists():
            self.skipTest("Run from synced PenguinOS Floral source root")
        self.assertIn(
            "vendor.lineage.touch-service.pixel",
            PIXEL_TOUCH.read_text(),
        )
        self.assertIn(
            "hal_lineage_touch_default_exec:s0",
            (PIXEL_SEPOLICY / "file_contexts").read_text(),
        )


if __name__ == "__main__":
    unittest.main()
