#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression checks for Knowles HAL access to Floral kernel UAPI headers."""

from pathlib import Path
import subprocess
import tempfile
import unittest

PATCH = Path(__file__).resolve().parents[1] / "patches/knowles-generated-kernel-headers.patch"
UPSTREAM = """// Minimal structure-equivalent version of pinned Knowles Android.bp
package {
    default_applicable_licenses: ["Android-Apache-2.0"],
}

use_sound_trigger_hal_cc_defaults {
    name: "use_sound_trigger_hal_defaults",
    header_libs: ["device_kernel_headers"],
    soong_config_variables: {
        use_sound_trigger_hal: {
            iaxxx: { enabled: true },
        },
    },
}
"""


class KnowlesGeneratedHeadersTest(unittest.TestCase):
    def test_patch_applies_and_is_reversible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "Android.bp"
            src.write_text(UPSTREAM)
            subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=root, check=True)
            subprocess.run(["git", "apply", str(PATCH)], cwd=root, check=True)
            updated = src.read_text()
            self.assertIn(
                'header_libs: ["device_kernel_headers", "generated_kernel_headers"]',
                updated,
            )
            self.assertEqual(updated.count('"generated_kernel_headers"'), 1)
            subprocess.run(["git", "apply", "--reverse", "--check", str(PATCH)],
                           cwd=root, check=True)

    def test_preparation_wires_the_patch(self):
        prepare = (Path(__file__).resolve().parents[1] / "tools/prepare.py").read_text()
        self.assertIn(
            '(Path("hardware/knowles/athletico/sound_trigger_hal"), '
            'PATCHES / "knowles-generated-kernel-headers.patch")',
            prepare,
        )


if __name__ == "__main__":
    unittest.main()
