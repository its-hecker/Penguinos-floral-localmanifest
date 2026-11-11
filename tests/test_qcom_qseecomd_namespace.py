"""Regression tests for PenguinOS Coral QSEEComD legacy display imports."""
from pathlib import Path
import tempfile
import unittest

from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces

PATHS = (
    Path("vendor/qcom/common/vendor/qseecomd-legacy/Android.bp"),
    Path("vendor/qcom/common/vendor/qseecomd/Android.bp"),
)
PROVIDER = "vendor/qcom/opensource/display"
MODULE = "libdisplayconfig.qti"


class QseecomdSoongTests(unittest.TestCase):
    def test_expected_namespace_targets(self):
        found = [(p, ns, lib) for p, ns, lib in TARGETS if p in PATHS]
        self.assertGreaterEqual(len(TARGETS), 10)
        self.assertEqual(set(found), {(p, PROVIDER, MODULE) for p in PATHS})

    def test_existing_keymaster_import_is_preserved(self):
        original = (
            'soong_namespace {\n'
            '    imports: ["vendor/qcom/common/vendor/keymaster"],\n'
            '}\n'
            'cc_library_shared { name: "libops", shared_libs: ["libdisplayconfig.qti"] }\n'
        )
        updated, changed = add_import(original, PROVIDER, MODULE)
        self.assertTrue(changed)
        self.assertIn('"vendor/qcom/common/vendor/keymaster"', updated)
        self.assertIn('"vendor/qcom/opensource/display"', updated)
        again, changed = add_import(updated, PROVIDER, MODULE)
        self.assertFalse(changed)
        self.assertEqual(again, updated)

    def test_idempotent_all_ten_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative, _, lib in TARGETS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(
                        'soong_namespace { imports: ["vendor/qcom/common/vendor/keymaster"] }\n',
                        encoding='utf-8',
                    )
                with path.open('a', encoding='utf-8') as out:
                    out.write(f'cc_library_shared {{ name: "synthetic", shared_libs: ["{lib}"] }}\n')
            self.assertEqual(len(fix_qcom_common_namespaces(root)), 10)
            for relative in PATHS:
                updated = (root / relative).read_text(encoding='utf-8')
                self.assertIn('"vendor/qcom/opensource/display"', updated)
                self.assertIn('"vendor/qcom/common/vendor/keymaster"', updated)
            self.assertEqual(fix_qcom_common_namespaces(root), [])

    def test_rejects_missing_qseecomd_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative, _, lib in TARGETS:
                if relative == PATHS[-1]:
                    continue
                p = root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    p.write_text('soong_namespace {}\n', encoding='utf-8')
                with p.open('a', encoding='utf-8') as out:
                    out.write(f'cc_library_shared {{ shared_libs: ["{lib}"] }}\n')
            untouched = root / TARGETS[0][0]
            original = untouched.read_text(encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                fix_qcom_common_namespaces(root)
            self.assertEqual(untouched.read_text(encoding='utf-8'), original)


if __name__ == '__main__':
    unittest.main()
