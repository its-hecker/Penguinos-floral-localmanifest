"""Coral perf module libqti-perfd uses the open-source display provider."""
from pathlib import Path
import tempfile
import unittest
from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces

PERF = Path('vendor/qcom/common/vendor/perf/Android.bp')
PROVIDER = 'vendor/qcom/opensource/display'
LIBRARY = 'libdisplayconfig.qti'


def make_fixture(root: Path, omit_perf: bool = False):
    for index, (relative, _, library) in enumerate(TARGETS):
        f = root / relative
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text('soong_namespace { imports: ["vendor/qcom/common/vendor/keymaster"] }\n')
        if omit_perf and relative == PERF:
            continue
        with f.open('a', encoding='utf-8') as stream:
            stream.write(f'cc_library_shared {{ name: "fixture{index}", shared_libs: ["{library}"] }}\n')


class PerfNamespaceTests(unittest.TestCase):
    def test_only_one_perf_target_and_other_imports_retained(self):
        self.assertEqual(
            [entry for entry in TARGETS if entry[0] == PERF],
            [(PERF, PROVIDER, LIBRARY)],
        )
        self.assertGreaterEqual(len(TARGETS), 12)

    def test_perf_existing_imports_are_preserved(self):
        before = (
            'soong_namespace {\n'
            '    imports: ["vendor/qcom/common/vendor/display/4.19", '
            '"vendor/qcom/common/vendor/display/5.15"],\n'
            '}\n'
            'cc_library_shared { name: "libqti-perfd", shared_libs: ["libdisplayconfig.qti"] }\n'
        )
        edited, changed = add_import(before, PROVIDER, LIBRARY)
        self.assertTrue(changed)
        self.assertIn('"vendor/qcom/opensource/display"', edited)
        self.assertIn('"vendor/qcom/common/vendor/display/4.19"', edited)
        self.assertIn('"vendor/qcom/common/vendor/display/5.15"', edited)
        self.assertEqual(add_import(edited, PROVIDER, LIBRARY), (edited, False))

    def test_all_namespace_changes_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_fixture(base)
            changed = fix_qcom_common_namespaces(base)
            self.assertEqual(len(changed), len({p for p, _, _ in TARGETS}))
            perf = (base / PERF).read_text(encoding='utf-8')
            self.assertIn('"vendor/qcom/opensource/display"', perf)
            self.assertIn('"vendor/qcom/common/vendor/keymaster"', perf)
            self.assertEqual(fix_qcom_common_namespaces(base), [])

    def test_invalid_perf_reference_rejects_every_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_fixture(base, omit_perf=True)
            first = base / TARGETS[0][0]
            previous = first.read_text(encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'libdisplayconfig.qti'):
                fix_qcom_common_namespaces(base)
            self.assertEqual(first.read_text(encoding='utf-8'), previous)


if __name__ == '__main__':
    unittest.main()
