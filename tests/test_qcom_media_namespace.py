"""Regressions for Qualcomm 5.4/5.10 media/display namespace imports."""
from pathlib import Path
import tempfile
import unittest

from qcom_namespace import TARGETS, add_import, fix_qcom_common_namespaces

MEDIA54 = Path("vendor/qcom/common/vendor/media/5.4/Android.bp")
MEDIA510 = Path("vendor/qcom/common/vendor/media/5.10/Android.bp")
DISPLAY = "vendor/qcom/opensource/display"
SM8150 = "hardware/qcom/sm8150/display"
EXPECTED = {
    (MEDIA54, SM8150, "libgrallocutils"),
    (MEDIA54, DISPLAY, "libgralloc.qti"),
    (MEDIA54, DISPLAY, "libdisplayconfig.qti"),
    (MEDIA510, DISPLAY, "libqdMetaData"),
    (MEDIA510, SM8150, "libgrallocutils"),
    (MEDIA510, DISPLAY, "libgralloc.qti"),
    (MEDIA510, DISPLAY, "libdisplayconfig.qti"),
}


def prepare_fixture(root: Path, omit=None, absent=None):
    for index, (relative, _, module) in enumerate(TARGETS):
        if relative == absent:
            continue
        f = root / relative
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text(
                'soong_namespace { imports: ["vendor/qcom/common/vendor/keymaster"] }\n',
                encoding="utf-8"
            )
        if omit == (relative, module):
            continue
        with f.open('a', encoding="utf-8") as stream:
            stream.write(f'cc_library_shared {{ name: "fixture{index}", shared_libs: ["{module}"] }}\n')


class MediaSoongNamespaceTests(unittest.TestCase):
    def test_targets_cover_all_seven_logged_dependencies(self):
        edges = {(p, ns, lib) for p, ns, lib in TARGETS if p in (MEDIA54, MEDIA510)}
        self.assertEqual(edges, EXPECTED)
        self.assertEqual(len(TARGETS), 23)
        self.assertEqual(len({p for p, _, _ in TARGETS}), 17)

    def test_same_file_multiple_imports_kept_without_duplicates(self):
        text = (
            'soong_namespace { imports: ["vendor/qcom/common/vendor/media/5.4"] }\n'
            'cc_library_shared { shared_libs: ["libgrallocutils", "libgralloc.qti", '
            '"libdisplayconfig.qti", "libqdMetaData"] }\n'
        )
        for namespace, module in (
            (SM8150, "libgrallocutils"),
            (DISPLAY, "libgralloc.qti"),
            (DISPLAY, "libdisplayconfig.qti"),
            (DISPLAY, "libqdMetaData"),
        ):
            text, _ = add_import(text, namespace, module)
        self.assertEqual(text.count(f'"{DISPLAY}"'), 1)
        self.assertEqual(text.count(f'"{SM8150}"'), 1)
        self.assertIn('"vendor/qcom/common/vendor/media/5.4"', text)
        self.assertEqual(add_import(text, DISPLAY, "libqdMetaData"), (text, False))

    def test_full_namespace_fixes_are_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prepare_fixture(root)
            files = fix_qcom_common_namespaces(root)
            self.assertEqual(len(files), 17)
            for relative in (MEDIA54, MEDIA510):
                text = (root / relative).read_text(encoding="utf-8")
                self.assertIn(f'"{DISPLAY}"', text)
                self.assertIn(f'"{SM8150}"', text)
                self.assertEqual(text.count(f'"{DISPLAY}"'), 1)
                self.assertEqual(text.count(f'"{SM8150}"'), 1)
            self.assertEqual(fix_qcom_common_namespaces(root), [])

    def test_missing_media_dependency_aborts_all_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prepare_fixture(root, omit=(MEDIA510, "libqdMetaData"))
            first = root / TARGETS[0][0]
            before = first.read_bytes()
            with self.assertRaisesRegex(ValueError, "libqdMetaData"):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_bytes(), before)

    def test_missing_media_file_aborts_all_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prepare_fixture(root, absent=MEDIA54)
            first = root / TARGETS[0][0]
            before = first.read_bytes()
            with self.assertRaises(FileNotFoundError):
                fix_qcom_common_namespaces(root)
            self.assertEqual(first.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
