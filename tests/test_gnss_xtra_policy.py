#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression checks for the Floral GNSS XTRA control property policy."""

from pathlib import Path
import unittest

DEVICE = Path("device/google/coral")
POLICY = DEVICE / "sepolicy"
PUBLIC = POLICY / "system_ext/public/property.te"
PRIVATE = POLICY / "system_ext/private/property_contexts"
GNSS = POLICY / "vendor/qcom/common/hal_gnss_qti.te"
CONFIG = POLICY / "coral-sepolicy.mk"


class GnssXtraPolicyTest(unittest.TestCase):
    def test_public_type_and_private_label(self):
        declaration = PUBLIC.read_text(encoding="utf-8")
        context = PRIVATE.read_text(encoding="utf-8")
        self.assertIn("system_restricted_prop(xtra_control_prop)", declaration)
        self.assertEqual(declaration.count("system_restricted_prop(xtra_control_prop)"), 1)
        self.assertIn(
            "persist.sys.xtra-daemon.enabled        u:object_r:xtra_control_prop:s0 exact bool",
            context,
        )
        self.assertEqual(context.count("persist.sys.xtra-daemon.enabled"), 1)

    def test_cross_partition_policy_is_enabled(self):
        config = CONFIG.read_text(encoding="utf-8")
        self.assertIn(
            "SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS += device/google/coral/sepolicy/system_ext/public",
            config,
        )
        self.assertIn(
            "SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += device/google/coral/sepolicy/system_ext/private",
            config,
        )
        self.assertIn(
            "BOARD_VENDOR_SEPOLICY_DIRS += device/google/coral/sepolicy/vendor/qcom/common",
            config,
        )

    def test_gnss_rule_remains_unmodified_and_restricted(self):
        rule = GNSS.read_text(encoding="utf-8")
        self.assertIn("dontaudit hal_gnss_qti xtra_control_prop:file r_file_perms;", rule)
        self.assertNotIn("permissive hal_gnss_qti", rule)


if __name__ == "__main__":
    unittest.main()
