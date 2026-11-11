"""Synthetic Soong regression checks; no Android source checkout required."""
import tempfile
import unittest
from pathlib import Path
from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces


class QcomNamespaceTests(unittest.TestCase):
    def test_no_imports_and_idempotent(self):
        original = 'soong_namespace {\n}\n\ncc_library {\n name: "a",\n shared_libs: ["libdisplaydebug"],\n}\n'
        changed, did_change = add_import(original, "hardware/qcom/sm8150/display", "libdisplaydebug")
        self.assertTrue(did_change)
        self.assertIn('"hardware/qcom/sm8150/display",', changed)
        same, did_change_again = add_import(changed, "hardware/qcom/sm8150/display", "libdisplaydebug")
        self.assertFalse(did_change_again)
        self.assertEqual(same, changed)

    def test_existing_imports_preserved(self):
        original = ('soong_namespace {\n    imports: [\n        "vendor/qcom/common/vendor/qseecomd",\n'
                    '    ],\n}\ncc_library_shared { shared_libs: ["libgps.utils"], }\n')
        edited, changed = add_import(original, "hardware/qcom/sm8150/gps", "libgps.utils")
        self.assertTrue(changed)
        self.assertIn('"vendor/qcom/common/vendor/qseecomd"', edited)
        self.assertIn('"hardware/qcom/sm8150/gps"', edited)

    def test_inline_imports(self):
        before = 'soong_namespace { imports: ["vendor/foo"] }\ncc_library { shared_libs: ["libdisplaydebug"], }'
        edited, changed = add_import(before, "hardware/qcom/sm8150/display", "libdisplaydebug")
        self.assertTrue(changed)
        self.assertIn('"hardware/qcom/sm8150/display",', edited)
        self.assertIn('"vendor/foo"', edited)

    def test_fails_without_namespace(self):
        with self.assertRaisesRegex(ValueError, 'soong_namespace'):
            add_import('cc_library { shared_libs: ["libdisplaydebug"] }', 'foo', 'libdisplaydebug')

    def test_fails_without_expected_reference(self):
        with self.assertRaisesRegex(ValueError, 'reference'):
            add_import('soong_namespace {}', 'foo', 'libdisplaydebug')

    def test_all_known_paths_and_atomic_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, _, lib in TARGETS:
                p = root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    p.write_text('soong_namespace {\n}\n')
                with p.open('a', encoding='utf-8') as out:
                    out.write(f'cc_library {{ shared_libs: ["{lib}"], }}\n')
            altered = fix_qcom_common_namespaces(root)
            self.assertEqual(len(altered), len({path for path, _, _ in TARGETS}))
            self.assertEqual(fix_qcom_common_namespaces(root), [])
            # Reject drift before changing any file.
            broken = root / TARGETS[-1][0]
            broken.write_text('soong_namespace {}\n')
            first = root / TARGETS[0][0]
            first.write_text('soong_namespace {}\ncc_library { shared_libs: ["libdisplaydebug"] }')
            before = first.read_text()
            with self.assertRaisesRegex(ValueError, 'reference'):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_text(), before)


if __name__ == '__main__':
    unittest.main()
