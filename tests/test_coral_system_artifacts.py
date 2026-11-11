"""Coral GSI ownership regression checks, using realistic synthetic makefiles."""
from pathlib import Path
import tempfile
import unittest

from coral_system import (
    GENERIC, CORAL_PRODUCT, LOCAL_GENERIC, OWNERSHIP,
    UPSTREAM_INHERIT, CORAL_INHERIT, HEADER, prepare_coral_system,
)

GENERIC_FIXTURE = '# Mock synced generic_system.mk\n$(call inherit-product, $(SRC_TARGET_DIR)/product/handheld_system.mk)\nPRODUCT_PACKAGES += curl telephony-ext GooglePackageInstaller\nPRODUCT_SYSTEM_PROPERTIES += ro.config.media_vol_steps=30\nDEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += vendor/aospa/target/config/aospa_vendor_framework_compatibility_matrix.xml\n$(call require-artifacts-in-path-relaxed, $(_my_paths), $(_my_allowed_list))\n'
PRODUCT_FIXTURE = 'PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS := relaxed\n$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_system.mk)\nPRODUCT_ARTIFACT_PATH_REQUIREMENT_ALLOWED_LIST += system/priv-app/TagGoogle/%\ninclude device/google/coral/coral/device.mk\n'


def fixture(root: Path, generic=GENERIC_FIXTURE, product=PRODUCT_FIXTURE):
    g = root / GENERIC
    p = root / CORAL_PRODUCT
    g.parent.mkdir(parents=True, exist_ok=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(generic, encoding="utf-8")
    p.write_text(product, encoding="utf-8")


class CoralArtifactTests(unittest.TestCase):
    def test_preserves_every_generic_system_setting_except_ownership(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            changed = prepare_coral_system(root)
            self.assertEqual(set(changed), {root / CORAL_PRODUCT, root / LOCAL_GENERIC})
            result = (root / LOCAL_GENERIC).read_text()
            self.assertTrue(result.startswith(HEADER))
            self.assertNotIn(OWNERSHIP, result)
            for marker in ("curl", "telephony-ext", "GooglePackageInstaller",
                           "ro.config.media_vol_steps", "DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE"):
                self.assertIn(marker, result)
            self.assertEqual((root / GENERIC).read_text(), GENERIC_FIXTURE)
            prod = (root / CORAL_PRODUCT).read_text()
            self.assertIn(CORAL_INHERIT, prod)
            self.assertNotIn(UPSTREAM_INHERIT, prod)
            self.assertIn("PRODUCT_ARTIFACT_PATH_REQUIREMENT_ALLOWED_LIST", prod)

    def test_idempotent_and_regenerates_when_synced_gsi_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            prepare_coral_system(root)
            self.assertEqual(prepare_coral_system(root), [])
            (root / GENERIC).write_text(GENERIC_FIXTURE + "# upstream comment\n")
            self.assertEqual(prepare_coral_system(root), [root / LOCAL_GENERIC])
            self.assertIn("# upstream comment", (root / LOCAL_GENERIC).read_text())

    def test_rejects_changed_upstream_without_modification(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, generic=GENERIC_FIXTURE.replace(OWNERSHIP, ""))
            old = (root / CORAL_PRODUCT).read_bytes()
            with self.assertRaisesRegex(ValueError, "Unexpected generic_system"):
                prepare_coral_system(root)
            self.assertEqual((root / CORAL_PRODUCT).read_bytes(), old)
            self.assertFalse((root / LOCAL_GENERIC).exists())

    def test_rejects_changed_product_without_modification(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, product=PRODUCT_FIXTURE.replace(UPSTREAM_INHERIT, ""))
            with self.assertRaisesRegex(ValueError, "inheritance"):
                prepare_coral_system(root)
            self.assertFalse((root / LOCAL_GENERIC).exists())

    def test_does_not_change_other_devices(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            flame = root / "device/google/coral/aospa_flame.mk"
            flame.write_text("Flame build remains untouched\n")
            prepare_coral_system(root)
            self.assertEqual(flame.read_text(), "Flame build remains untouched\n")


if __name__ == "__main__":
    unittest.main()
