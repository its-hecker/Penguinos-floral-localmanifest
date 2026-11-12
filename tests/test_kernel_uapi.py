#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression checks for Floral kernel UAPI preparation."""

from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import kernel_uapi


class KernelUapiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in kernel_uapi.REQUIRED:
            source = self.root / kernel_uapi.KERNEL_PATH / "include/uapi" / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("kernel UAPI source\n")

    def test_make_installs_expected_headers_into_soong_path(self):
        expected = self.root / "out" / kernel_uapi.GENERATOR_REL

        def install(cmd, **kwargs):
            self.assertEqual(
                cmd,
                [
                    "make",
                    "-C",
                    str(self.root / kernel_uapi.KERNEL_PATH),
                    f"O={expected}",
                    "ARCH=arm64",
                    "headers_install",
                ],
            )
            self.assertEqual(kwargs["cwd"], self.root)
            for name in kernel_uapi.REQUIRED:
                dest = expected / "usr/include" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text("sanitized UAPI\n")

        with patch.dict(os.environ, {"OUT_DIR": "out"}):
            with patch.object(kernel_uapi.subprocess, "run", side_effect=install):
                self.assertEqual(kernel_uapi.install_headers(self.root), expected)

    def test_preparation_fails_when_make_only_produces_dummy_dep(self):
        output = self.root / "out" / kernel_uapi.GENERATOR_REL
        output.mkdir(parents=True)
        (output / ".dummy_dep").touch()
        with patch.object(kernel_uapi.subprocess, "run", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "installation incomplete"):
                kernel_uapi.install_headers(self.root, "out")

    def test_preparation_fails_if_kernel_header_source_is_missing(self):
        (self.root / kernel_uapi.KERNEL_PATH /
         "include/uapi/drm/sde_drm.h").unlink()
        with self.assertRaises(FileNotFoundError):
            kernel_uapi.install_headers(self.root, "out")

    def test_custom_out_dir(self):
        expected = self.root / "custom_out" / kernel_uapi.GENERATOR_REL

        def install(cmd, **_kwargs):
            self.assertIn(f"O={expected}", cmd)
            for name in kernel_uapi.REQUIRED:
                header = expected / "usr/include" / name
                header.parent.mkdir(parents=True, exist_ok=True)
                header.write_text("header")

        with patch.object(kernel_uapi.subprocess, "run", side_effect=install):
            self.assertEqual(
                kernel_uapi.install_headers(self.root, "custom_out"), expected
            )


if __name__ == "__main__":
    unittest.main()
