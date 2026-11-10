#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare the Floral hardware integrations against the synced PenguinOS sources."""

import argparse
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from camera_install import configure as configure_camera
from google_camera import prepare as prepare_google_camera


FACE = Path("vendor/hecker/floral/faceid")
MOTION = Path("vendor/hecker/floral/motionsense")
DEVICE = Path("device/google/coral")
KERNEL = Path("kernel/google/msm-4.14")
PATCHES = Path(__file__).resolve().parents[1] / "patches"


def plugin_tool(plugin, tool, *arguments):
    subprocess.run([sys.executable, plugin / "tools" / tool, *arguments], check=True)


def patch_needed(project, patch):
    command = ["git", "-C", project, "apply"]
    if subprocess.run([*command, "--reverse", "--check", patch],
                      capture_output=True).returncode == 0:
        return False
    subprocess.run([*command, "--check", patch], check=True)
    return True


def overlay_arrays(directories, name, option):
    arguments = []
    for directory in directories:
        for path in sorted(directory.glob("*.xml")):
            if any(node.get("name") == name for node in ET.parse(path).getroot()):
                arguments.extend((option, path))
    return arguments


def prepare(device, offline):
    vendor = Path("vendor/google") / device
    if not (DEVICE / f"aospa_{device}.mk").is_file() or not (vendor / "Android.bp").is_file():
        raise ValueError(f"Sync the PenguinOS {device} manifest from the ROM source root first")
    defconfig = (KERNEL / "arch/arm64/configs/floral_defconfig").read_text().splitlines()
    if "CONFIG_KSU=y" not in defconfig or not (KERNEL / "KernelSU/kernel/Kconfig").is_file():
        raise ValueError("The Floral KernelSU Next source or defconfig is missing. Sync kernel submodules.")

    patches = [(Path("vendor/aospa"), PATCHES / "aospa-floral.patch"),
               (Path("device/qcom/kernelscripts"), PATCHES / "legacy-kernel-task.patch")]
    if device == "coral":
        patches.extend([
            (Path("vendor/aospa"), PATCHES / "aospa-stop-on-lunch-error.patch"),
            (Path("hardware/qcom-caf/common"), PATCHES / "qcom-caf-soong-providers.patch"),
            (Path("hardware/lineage/compat"), PATCHES / "lineage-compat-hidl-providers.patch"),
            # Celerity provides the Qualcomm display interfaces in Soong's global namespace.
            (Path("hardware/qcom-caf/common"), PATCHES / "qcom-caf-display-namespace.patch"),
            (Path("hardware/qcom/sm8150/display"), PATCHES / "sm8150-display-namespace.patch"),
            (Path("vendor/qcom/opensource/display"), PATCHES / "qcom-display-namespace.patch"),
        ])
    pending = [(project, patch) for project, patch in patches if patch_needed(project, patch)]
    plugin_tool(FACE, "apply_framework_fixes.py", "--check")
    configure_camera(Path.cwd())
    prepare_google_camera(Path.cwd(), offline=offline)

    for plugin in (MOTION, FACE):
        fetch_options = ("--verify-only",) if offline else ()
        plugin_tool(plugin, "fetch_prebuilts.py", *fetch_options)
        plugin_tool(plugin, "check_port.py")

    overlays = [Path("vendor/aospa/overlay/static"), DEVICE / "overlay",
                DEVICE / "overlay-lineage", DEVICE / device / "overlay"]
    aospa_overlay = Path("vendor/aospa/overlay")
    motion_args = overlay_arrays(
        [*(root / "frameworks/base/packages/SystemUI/res/values" for root in overlays),
         aospa_overlay / "AOSPASystemUIOverlay/res/values"],
        "config_pluginAllowlist", "--allowlist-xml")
    face_args = overlay_arrays(
        [*(root / "frameworks/base/core/res/res/values" for root in overlays),
         aospa_overlay / "AOSPAFrameworksOverlay/res/values"],
        "config_biometric_sensors", "--biometrics-xml")

    for project, patch in pending:
        subprocess.run(["git", "-C", project, "apply", patch], check=True)
    plugin_tool(FACE, "apply_framework_fixes.py", "--apply")
    configure_camera(Path.cwd(), write=True)
    plugin_tool(MOTION, "prepare.py", "--policy-dir", DEVICE / "sepolicy", *motion_args)
    plugin_tool(FACE, "prepare.py", "--vendor-tree", vendor, *face_args)
    for plugin in (MOTION, FACE):
        plugin_tool(plugin, "verify_ready.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", choices=("coral", "flame"))
    parser.add_argument("--offline", action="store_true", help="Use verified cached prebuilts")
    args = parser.parse_args()
    try:
        prepare(args.device, args.offline)
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"PenguinOS Floral setup: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
