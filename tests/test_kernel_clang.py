#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Preflight checks for the Floral Android 17 kernel compiler."""

from pathlib import Path
import re
import subprocess
import unittest

BOARD = Path("device/google/coral/BoardConfig-common.mk")
BUILD = Path(".repo/local_manifests/build.sh")
KERNEL_BUILD_CONFIG = Path("vendor/hecker/floral/kernel-build/config/BoardConfigKernel.mk")


class KernelClangTest(unittest.TestCase):
    def test_kernel_uses_pinned_android_17_toolchain(self):
        source = BOARD.read_text()
        match = re.search(r"(?m)^TARGET_KERNEL_CLANG_VERSION\s*:=\s*(r[\w.-]+)\s*$", source)
        self.assertIsNotNone(match, "Floral BoardConfig must pin kernel Clang")
        self.assertEqual(match.group(1), "r584948b")

    def test_pinned_prebuilt_exists_and_runs(self):
        source = BOARD.read_text()
        match = re.search(r"(?m)^TARGET_KERNEL_CLANG_VERSION\s*:=\s*(r[\w.-]+)\s*$", source)
        self.assertIsNotNone(match)
        clang = Path("prebuilts/clang/host/linux-x86") / f"clang-{match.group(1)}" / "bin/clang"
        self.assertTrue(clang.is_file(), f"Missing pinned kernel compiler: {clang}")
        self.assertTrue(clang.stat().st_mode & 0o111, f"Compiler is not executable: {clang}")
        subprocess.run([str(clang), "--version"], check=True, capture_output=True)

    def test_pixelos_kernel_rules_use_the_version_pin(self):
        text = KERNEL_BUILD_CONFIG.read_text()
        self.assertIn("KERNEL_CLANG_VERSION := clang-$(TARGET_KERNEL_CLANG_VERSION)", text)
        self.assertIn("TARGET_KERNEL_CLANG_PATH ?=", text)

    def test_build_entrypoint_checks_clang(self):
        source = BUILD.read_text()
        self.assertIn("kernel_clang_version=$(sed", source)
        self.assertIn('"$kernel_clang" --version', source)


if __name__ == "__main__":
    unittest.main()
