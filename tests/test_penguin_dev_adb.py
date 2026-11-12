#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for temporary PenguinOS bootloop ADB access.

Run from the synced ROM root:
  python3 -m unittest discover -s .repo/local_manifests/tests -p 'test_penguin_dev_adb.py' -v
"""
import os
from pathlib import Path
import subprocess
import unittest

FRAGMENT = Path("device/google/coral/debugging/development_adb.mk")
CORAL = Path("device/google/coral/aospa_coral.mk")
FLAME = Path("device/google/coral/aospa_flame.mk")


class PenguinDevelopmentAdbTest(unittest.TestCase):
    def evaluate(self, variant, mode=None, inherited=()):
        source = "PRODUCT_PRODUCT_PROPERTIES := " + " ".join(inherited) + "\n"
        source += "include " + str(FRAGMENT) + "\n"
        source += 'all:\n\t@printf "%s\\n" $(PRODUCT_PRODUCT_PROPERTIES)\n'
        env = os.environ.copy()
        env.pop("PENGUIN_DEV_USB_ADB", None)
        if mode is not None:
            env["PENGUIN_DEV_USB_ADB"] = mode
        return subprocess.run(
            ["make", "--no-print-directory", "-f", "-", "TARGET_BUILD_VARIANT=" + variant],
            input=source, env=env, text=True, capture_output=True,
        )

    def values(self, variant, mode=None, inherited=()):
        result = self.evaluate(variant, mode, inherited)
        self.assertEqual(result.returncode, 0, result.stderr)
        items = result.stdout.splitlines()
        props = dict(item.split("=", 1) for item in items)
        self.assertEqual(len(items), len(props), "Duplicate product property assignments")
        return props

    def test_userdebug_and_eng_enable_usb_without_pc_prompt(self):
        for variant in ("userdebug", "eng"):
            with self.subTest(variant=variant):
                props = self.values(variant)
                self.assertEqual(props["ro.penguinos.dev_usb_adb"], "1")
                self.assertEqual(props["ro.adb.secure"], "0")
                self.assertEqual(props["persist.sys.usb.config"], "adb")
                self.assertNotIn("ro.secure", props)
                self.assertNotIn("service.adb.tcp.port", props)

    def test_release_mode_restores_normal_authorization(self):
        for variant in ("userdebug", "eng", "user"):
            with self.subTest(variant=variant):
                props = self.values(variant, "false", ("persist.sys.usb.config=mtp",))
                self.assertEqual(props["ro.penguinos.dev_usb_adb"], "0")
                self.assertEqual(props["ro.adb.secure"], "1")
                self.assertEqual(props["persist.sys.usb.config"], "mtp")

    def test_user_build_is_secure_and_rejects_unrestricted_adb(self):
        props = self.values("user")
        self.assertEqual(props["ro.penguinos.dev_usb_adb"], "0")
        self.assertEqual(props["ro.adb.secure"], "1")
        self.assertNotIn("persist.sys.usb.config", props)
        result = self.evaluate("user", "true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a userdebug or eng build", result.stderr)

    def test_inherited_properties_do_not_create_duplicate_assignments(self):
        props = self.values("userdebug", "true", (
            "ro.adb.secure=1", "ro.adb.secure?=1",
            "ro.penguinos.dev_usb_adb=0", "persist.sys.usb.config=mtp",
            "persist.sys.usb.config?=none", "other.prop=keep",
        ))
        self.assertEqual(props["ro.adb.secure"], "0")
        self.assertEqual(props["ro.penguinos.dev_usb_adb"], "1")
        self.assertEqual(props["persist.sys.usb.config"], "adb")
        self.assertEqual(props["other.prop"], "keep")

    def test_invalid_flags_are_rejected(self):
        for flag in ("1", "TRUE", "", "true false", "secure"):
            with self.subTest(flag=flag):
                r = self.evaluate("userdebug", flag)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("must be true or false", r.stderr)

    def test_both_device_products_include_debugging_after_plugins(self):
        for mk in (CORAL, FLAME):
            if not mk.is_file():
                self.skipTest(f"Needs synced device tree: {mk}")
            source = mk.read_text()
            self.assertEqual(source.count("debugging/development_adb.mk"), 1)
            self.assertGreater(
                source.index("debugging/development_adb.mk"),
                source.index("boot_diagnostics/boot_capture.mk"),
            )


if __name__ == "__main__":
    unittest.main()
