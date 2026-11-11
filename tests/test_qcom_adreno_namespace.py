"""Adreno namespace regression tests for PenguinOS Coral (synthetic fixtures)."""
from pathlib import Path
import tempfile
import unittest

from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces

ADRENO = tuple(
    Path(f"vendor/qcom/common/vendor/adreno/{version}/Android.bp")
    for version in ("r", "s", "t", "u")
)
PROVIDER = "vendor/qcom/opensource/display"
MODULE = "libgralloc.qti"


def populate(root, broken_path=None, broken_module=False):
    for n, (path, _, module) in enumerate(TARGETS):
        if path == broken_path and not broken_module:
            continue
        full = root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        if not full.exists():
            full.write_text(
                'soong_namespace { imports: ["vendor/qcom/common/vendor/keymaster"] }\n',
                encoding='utf-8'
            )
        if path == broken_path and broken_module:
            continue
        with full.open('a', encoding='utf-8') as stream:
            stream.write(f'cc_library_shared {{ name: "fixture{n}", shared_libs: ["{module}"] }}\n')


class AdrenoNamespaceTests(unittest.TestCase):
    def test_four_target_paths_and_provider(self):
        selected = [(path, namespace, lib) for path, namespace, lib in TARGETS if path in ADRENO]
        self.assertEqual(set(selected), {(path, PROVIDER, MODULE) for path in ADRENO})
        self.assertEqual(len(selected), 4)

    def test_preserves_existing_import_and_reapplies_safely(self):
        original = (
            'soong_namespace {\n    imports: ["vendor/qcom/common/vendor/perf"],\n}\n'
            'cc_library_shared { name: "libCB", shared_libs: ["libgralloc.qti"] }\n'
        )
        modified, changed = add_import(original, PROVIDER, MODULE)
        self.assertTrue(changed)
        self.assertIn('"vendor/qcom/common/vendor/perf"', modified)
        self.assertIn('"vendor/qcom/opensource/display"', modified)
        self.assertEqual(add_import(modified, PROVIDER, MODULE), (modified, False))

    def test_all_targets_preserved_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            populate(root)
            changed = fix_qcom_common_namespaces(root)
            self.assertEqual(len(changed), len({p for p, _, _ in TARGETS}))
            for path in ADRENO:
                text = (root / path).read_text(encoding='utf-8')
                self.assertIn('"vendor/qcom/opensource/display"', text)
                self.assertIn('"vendor/qcom/common/vendor/keymaster"', text)
            self.assertEqual(fix_qcom_common_namespaces(root), [])

    def test_missing_adreno_file_rejects_all_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            populate(root, broken_path=ADRENO[-1])
            first = root / TARGETS[0][0]
            previous = first.read_bytes()
            with self.assertRaises(FileNotFoundError):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_bytes(), previous)

    def test_missing_adreno_dependency_rejects_all_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            populate(root, broken_path=ADRENO[-1], broken_module=True)
            first = root / TARGETS[0][0]
            previous = first.read_bytes()
            with self.assertRaisesRegex(ValueError, 'libgralloc.qti'):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
