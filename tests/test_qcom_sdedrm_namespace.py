"""Synthetic regression tests for Coral's dual dependency imports in 5.15."""
from pathlib import Path
import tempfile
import unittest

from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces

DISPLAY = Path('vendor/qcom/common/vendor/display/5.15/Android.bp')
PROVIDER = 'vendor/qcom/common/vendor/display/4.14'


def fixture(root: Path, omit_sdedrm=False):
    for index, (relative, _, module) in enumerate(TARGETS):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(
                'soong_namespace { imports: ["vendor/qcom/common/vendor/qseecomd"] }\n',
                encoding='utf-8',
            )
        if omit_sdedrm and module == 'libsdedrm':
            continue
        with path.open('a', encoding='utf-8') as f:
            f.write(f'cc_library {{ name: "t{index}", shared_libs: ["{module}"] }}\n')


class SdedrmNamespaceTests(unittest.TestCase):
    def test_conflicting_tree_imports_are_specific(self):
        target_entries = [(p, namespace, module) for p, namespace, module in TARGETS if p == DISPLAY]
        self.assertEqual(set(target_entries), {
            (DISPLAY, 'hardware/qcom/sm8150/display', 'libdisplaydebug'),
            (DISPLAY, PROVIDER, 'libsdedrm'),
        })
        self.assertGreaterEqual(len(TARGETS), 11)

    def test_fix_keeps_both_imports_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            affected = fix_qcom_common_namespaces(root)
            self.assertEqual(len(affected), len({p for p, _, _ in TARGETS}))
            self.assertEqual(len(affected), len({p for p, _, _ in TARGETS}))
            self.assertEqual(affected.count(root / DISPLAY), 1)
            text = (root / DISPLAY).read_text(encoding='utf-8')
            for imported in (PROVIDER, 'hardware/qcom/sm8150/display',
                             'vendor/qcom/common/vendor/qseecomd'):
                self.assertIn('"' + imported + '"', text)
            self.assertEqual(fix_qcom_common_namespaces(root), [])

    def test_missing_reference_rejects_all_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, omit_sdedrm=True)
            first = root / TARGETS[0][0]
            old = first.read_text(encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'libsdedrm'):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_text(encoding='utf-8'), old)


if __name__ == '__main__':
    unittest.main()
