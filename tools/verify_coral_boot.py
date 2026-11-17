#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the Coral boot files and partition metadata before flashing."""

import argparse
from pathlib import Path
import struct
import sys
from zipfile import BadZipFile, ZipFile


def properties(archive, entry):
    lines = archive.read(entry).decode().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify(product_out, debug_adb):
    target_files = product_out / "obj/PACKAGING/target_files_intermediates/aospa_coral-target_files.zip"
    with ZipFile(target_files) as target:
        partitions = properties(target, "META/dynamic_partitions_info.txt")
        misc = properties(target, "META/misc_info.txt")
        timestamp = properties(target, "SYSTEM/build.prop")["ro.build.date.utc"]
        check(misc.get("ab_update") == "true", "Build must use A/B updates")
        check(partitions.get("virtual_ab") != "true", "Virtual A/B is enabled")
        check(partitions.get("super_partition_size") == "9755951104", "Unexpected Coral super size")
        check(partitions.get("super_google_dynamic_partitions_group_size") == "4873781248",
              "Unexpected Coral slot size")
        check(set(partitions.get("dynamic_partition_list", "").split()) ==
              {"system", "system_ext", "vendor", "product"}, "Unexpected dynamic partition list")
        product_props = properties(target, "PRODUCT/etc/build.prop")
        check(product_props.get("ro.bpf.kver_override") == "5.10.239",
              "Missing Coral BPF compatibility property")
        if debug_adb:
            vendor_props = properties(target, "VENDOR/build.prop")
            check(product_props.get("ro.adb.secure") == "0" and
                  vendor_props.get("ro.vendor.penguinos.coral_early_adb") == "true",
                  "Expected the private development ADB properties")
            target.getinfo("SYSTEM/etc/init/pixelos-boot-capture.rc")

        fstab = target.read("BOOT/RAMDISK/first_stage_ramdisk/fstab.sm8150").decode()
        mounts = {fields[1] for line in fstab.splitlines() if (fields := line.split()) and
                  not fields[0].startswith("#") and len(fields) >= 5 and
                  "first_stage_mount" in fields[4].split(",")}
        check({"/system", "/system_ext", "/vendor", "/product", "/metadata"} <= mounts,
              "Incomplete first-stage ramdisk fstab")

        for image in ("dtbo.img", "vbmeta.img"):
            check(target.getinfo(f"IMAGES/{image}").file_size > 0, f"Missing packaged {image}")
        with target.open("IMAGES/boot.img") as boot:
            header = boot.read(1660)
        check(len(header) == 1660 and header[:8] == b"ANDROID!", "Invalid boot image header")
        check(struct.unpack_from("<II", header, 36) == (4096, 2),
              "Coral boot image must use header v2 and 4096-byte pages")
        check(all(struct.unpack_from("<I", header, offset)[0] for offset in (8, 16, 1648)),
              "Boot image is missing its kernel, ramdisk or DTB")

    with ZipFile(product_out / "aospa_coral-ota.zip") as ota:
        metadata = properties(ota, "META-INF/com/android/metadata")
        check(metadata.get("ota-type") == "AB" and metadata.get("pre-device") == "coral",
              "OTA must target Coral and use A/B")
        check(metadata.get("post-timestamp") == timestamp, "OTA and target-files builds differ")
        check("pre-build" not in metadata and ota.getinfo("payload.bin").file_size > 0,
              "OTA must have a full payload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product_out", type=Path)
    parser.add_argument("--debug-adb", action="store_true", help="Require private USB ADB settings")
    args = parser.parse_args()
    try:
        verify(args.product_out, args.debug_adb)
    except (BadZipFile, KeyError, OSError, ValueError) as error:
        sys.exit(f"Coral boot files: {error}")
    print(f"Checked Coral boot images and full A/B OTA in {args.product_out}")
