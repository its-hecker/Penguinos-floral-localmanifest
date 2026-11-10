import tempfile
import unittest
from pathlib import Path
from libgui_compat import (fix_libgui_vendor_shims, update_shim_dependencies,
                           provider_supports_vendor)
from inject_prepare import update_prepare

GUI = '''cc_library_shared {
    name: "libgui",
    vendor_available: true,
    double_loadable: true,
}
'''
SOURCE = '''cc_library {
    name: "libgui_shim_vendor",
    defaults: ["libgui_shim_defaults"],
    shared_libs: ["libgui_vendor"],
    vendor: true,
}

cc_library_shared {
    name: "libgui_buffer_shim_vendor",
    defaults: ["libgui_shim_defaults"],
    srcs: ["libgui/BufferItemConsumer.cpp"],
    shared_libs: [
        "libgui_vendor",
        "libutils",
    ],
    compile_multilib: "64",
    vendor: true,
}

cc_library {
    name: "other_module",
    shared_libs: ["libgui_vendor"],
}
'''
PREPARE = '''from qcom_namespace import fix_qcom_common_namespaces


def prepare(device, offline):
    if device == "coral":
        fix_qcom_common_namespaces(Path.cwd())
'''

class GuiCompatTests(unittest.TestCase):
    def test_provider_vendor_variant(self):
        self.assertTrue(provider_supports_vendor(GUI))
        self.assertFalse(provider_supports_vendor(GUI.replace("true", "false")))

    def test_exactly_two_shims_changed(self):
        updated, names = update_shim_dependencies(SOURCE)
        self.assertEqual(len(names), 2)
        self.assertIn('shared_libs: ["libgui"]', updated)
        self.assertIn('"libgui",\n        "libutils",', updated)
        self.assertEqual(updated.count('"libgui_vendor"'), 1)
        self.assertEqual(update_shim_dependencies(updated), (updated, []))

    def test_missing_shim_fails_without_changes(self):
        with self.assertRaises(ValueError):
            update_shim_dependencies(SOURCE.replace('name: "libgui_shim_vendor"', 'name: "removed_shim"'))

    def test_full_patch_reapplication_and_vendor_guard(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / "hardware/lineage/compat/Android.bp"
            gui = root / "frameworks/native/libs/gui/Android.bp"
            p.parent.mkdir(parents=True)
            gui.parent.mkdir(parents=True)
            p.write_text(SOURCE)
            gui.write_text(GUI)
            self.assertEqual(len(fix_libgui_vendor_shims(root)), 2)
            self.assertEqual(fix_libgui_vendor_shims(root), [])
            gui.write_text(GUI.replace("true", "false"))
            with self.assertRaises(ValueError):
                fix_libgui_vendor_shims(root)

    def test_hook_idempotence(self):
        edited, changed = update_prepare(PREPARE)
        self.assertTrue(changed)
        self.assertIn('from libgui_compat import fix_libgui_vendor_shims', edited)
        self.assertIn('        fix_libgui_vendor_shims(Path.cwd())', edited)
        self.assertEqual(update_prepare(edited), (edited, False))

    def test_partial_hook_is_rejected(self):
        with self.assertRaises(ValueError):
            update_prepare(PREPARE + 'from libgui_compat import fix_libgui_vendor_shims\n')

if __name__ == "__main__":
    unittest.main()
