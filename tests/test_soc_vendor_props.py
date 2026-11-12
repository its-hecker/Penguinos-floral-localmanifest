#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Ensure Floral does not conflict with PenguinOS-generated SoC properties."""

from pathlib import Path
import re
import unittest


class FloralSocVendorPropsTest(unittest.TestCase):
    def setUp(self):
        self.vendor = Path("device/google/coral/vendor.prop").read_text()
        self.device_mk = Path("device/google/coral/device-common.mk").read_text()

    def test_manufacturer_is_supplied_by_platform_only(self):
        manual = re.findall(r"(?m)^\s*ro\.soc\.manufacturer\s*=", self.vendor)
        self.assertEqual(
            manual, [],
            "Remove manual ro.soc.manufacturer: PenguinOS also generates QTI",
        )

    def test_soc_model_remains_in_vendor_prop(self):
        models = re.findall(
            r"(?m)^ro\.soc\.model\s*=\s*([^\n#]+)\s*$",
            self.vendor,
        )
        self.assertEqual(models, ["SM8150"])

    def test_device_tree_still_loads_vendor_prop(self):
        self.assertIn("TARGET_VENDOR_PROP := $(LOCAL_PATH)/vendor.prop", self.device_mk)


if __name__ == "__main__":
    unittest.main()
