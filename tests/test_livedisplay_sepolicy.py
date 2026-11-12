#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the Floral LiveDisplay vendor SELinux policy dependency closure."""

from pathlib import Path
import re
import unittest

DEVICE = Path("device/google/coral")
SYSTEM_EXT = DEVICE / "sepolicy/system_ext/public"
VENDOR = DEVICE / "sepolicy/vendor/lineage"


class FloralLiveDisplaySePolicyTest(unittest.TestCase):
    def setUp(self):
        self.mk = (DEVICE / "sepolicy/coral-sepolicy.mk").read_text()
        self.attrs = (SYSTEM_EXT / "attributes").read_text()
        self.te = (VENDOR / "hal_lineage_livedisplay.te").read_text()
        self.contexts = (VENDOR / "service_contexts").read_text()

    def test_policy_directories_are_compiled(self):
        self.assertIn(
            "SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS += device/google/coral/sepolicy/system_ext/public",
            self.mk,
        )
        self.assertIn(
            "BOARD_VENDOR_SEPOLICY_DIRS += device/google/coral/sepolicy/vendor/lineage",
            self.mk,
        )

    def test_livedisplay_hal_server_attributes_declared(self):
        # AOSP hal_attribute expands to hal_*, hal_*_client, hal_*_server.
        self.assertRegex(self.attrs, r"(?m)^hal_attribute\(lineage_livedisplay\)$")
        self.assertIn(
            "hal_server_domain(hal_lineage_livedisplay_qti, hal_lineage_livedisplay)",
            self.te,
        )

    def test_livedisplay_has_typed_service_and_client_bindings(self):
        self.assertIn(
            "type hal_lineage_livedisplay_service, hal_service_type, service_manager_type;",
            self.te,
        )
        self.assertIn(
            "hal_attribute_service(hal_lineage_livedisplay, hal_lineage_livedisplay_service)",
            self.te,
        )
        self.assertIn(
            "binder_call(hal_lineage_livedisplay_client, hal_lineage_livedisplay_server)",
            self.te,
        )
        services = [
            line.split()[0]
            for line in self.contexts.splitlines()
            if line and not line.startswith("#")
        ]
        self.assertGreaterEqual(len(services), 10)
        self.assertEqual(len(services), len(set(services)))
        for line in self.contexts.splitlines():
            if not line or line.startswith("#"):
                continue
            self.assertRegex(
                line,
                r"^vendor\.lineage\.livedisplay\.\w+/default\s+u:object_r:hal_lineage_livedisplay_service:s0$",
            )


if __name__ == "__main__":
    unittest.main()
