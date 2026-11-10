"""Tests for PenguinOS Coral's legacy Qualcomm WLAN namespace fix."""
from pathlib import Path
import tempfile
import unittest

from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces

WLAN = {
    Path("vendor/qcom/common/vendor/wlan/Android.bp"),
    Path("vendor/qcom/common/vendor/wlan-legacy/Android.bp"),
}


class WlanNamespaceTests(unittest.TestCase):
    def test_wlan_targets_match_log(self):
        found = {(p, ns, mod) for (p, ns, mod) in TARGETS if p in WLAN}
        self.assertEqual(
            found,
            {(p, "hardware/qcom/wlan/legacy", "libcld80211") for p in WLAN},
        )
        self.assertGreaterEqual(len(TARGETS), 8)

    def test_wlan_module_resolves_with_existing_imports(self):
        original = (
            'soong_namespace {\n'
            '    imports: ["vendor/qcom/common/vendor/qseecomd"],\n'
            '}\n'
            'cc_binary { name: "cnss-daemon", shared_libs: ["libcld80211"] }\n'
        )
        updated, did_change = add_import(
            original, "hardware/qcom/wlan/legacy", "libcld80211"
        )
        self.assertTrue(did_change)
        self.assertIn('"hardware/qcom/wlan/legacy",', updated)
        self.assertIn('"vendor/qcom/common/vendor/qseecomd"', updated)
        again, changed = add_import(
            updated, "hardware/qcom/wlan/legacy", "libcld80211"
        )
        self.assertFalse(changed)
        self.assertEqual(again, updated)

    def test_full_fix_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for path, _, module in TARGETS:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    f'soong_namespace {{}}\n'
                    f'cc_binary {{ shared_libs: ["{module}"], }}\n',
                    encoding="utf-8",
                )

            changed = fix_qcom_common_namespaces(root)
            self.assertEqual(len(changed), len(TARGETS))
            for relative in WLAN:
                self.assertIn(
                    '"hardware/qcom/wlan/legacy"',
                    (root / relative).read_text(encoding="utf-8"),
                )
            self.assertEqual(fix_qcom_common_namespaces(root), [])

    def test_does_not_write_any_targets_when_wlan_source_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for relative, _, module in TARGETS:
                if relative == Path("vendor/qcom/common/vendor/wlan-legacy/Android.bp"):
                    continue
                p = root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    f'soong_namespace {{}}\ncc_binary {{shared_libs: ["{module}"]}}',
                    encoding="utf-8",
                )
            first = root / TARGETS[0][0]
            before = first.read_text(encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
