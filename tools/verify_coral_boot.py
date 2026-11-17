#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the Coral boot files and partition metadata before flashing."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from zipfile import BadZipFile, ZipFile


SLOT_BYTES = 4873781248
DYNAMIC_PARTITIONS = ("system", "system_ext", "vendor", "product")
FACEID_LOCK = Path("vendor/hecker/floral/faceid/prebuilts.lock.json")
KEYMASTER_FILES = {
    "bin/hw/android.hardware.keymaster@4.1-service.citadel":
        "proprietary/vendor/bin/hw/android.hardware.keymaster@4.1-service.citadel",
    "lib64/android.hardware.keymaster@4.1-impl.nos.so":
        "proprietary/vendor/lib64/android.hardware.keymaster@4.1-impl.nos.so",
    "lib64/libcrypto-v33.so": "proprietary/compat/libcrypto-v33.so",
}


def properties(archive, entry):
    lines = archive.read(entry).decode().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def partition_image_size(target, name):
    entry = f"IMAGES/{name}.img"
    with target.open(entry) as image:
        header = image.read(28)
    check(header, f"Empty {name} image")
    if header[:4] != b"\x3a\xff\x26\xed":
        return target.getinfo(entry).file_size
    check(len(header) == 28, f"Truncated sparse {name} image")
    block_size, blocks = struct.unpack_from("<II", header, 12)
    check(block_size > 0 and blocks > 0, f"Invalid sparse size for {name}")
    return block_size * blocks


def verify_keymaster(target):
    lock = json.loads(FACEID_LOCK.read_text())
    hashes = {entry["destination"]: entry["sha256"] for entry in lock["artifacts"]}
    for path, reference in KEYMASTER_FILES.items():
        digest = hashlib.sha256(target.read(f"VENDOR/{path}")).hexdigest()
        check(digest == hashes[reference], f"Vendor {path} differs from the pinned Citadel build")
    service = target.read("VENDOR/etc/init/floral-faceid-citadel.rc").decode().splitlines()
    check("    override" in service and "    user hsm" in service and "    group hsm drmrpc" in service,
          "Missing Citadel init service settings")


def verify_boot_images(target):
    entry = "IMAGES/boot.img"
    check(target.getinfo(entry).file_size <= 64 * 1024 * 1024, "Boot image exceeds 64 MiB")
    with target.open(entry) as boot:
        header = boot.read(1660)
        check(len(header) == 1660 and header[:8] == b"ANDROID!", "Invalid boot image header")
        page_size, version = struct.unpack_from("<II", header, 36)
        check((page_size, version) == (4096, 2), "Coral boot image needs v2 and 4096-byte pages")
        kernel, ramdisk, second = struct.unpack_from("<I4xI4xI", header, 8)
        recovery_dtbo = struct.unpack_from("<I", header, 1632)[0]
        dtb = struct.unpack_from("<I", header, 1648)[0]
        check(kernel and ramdisk and dtb, "Boot image is missing its kernel, ramdisk or DTB")
        dtb_offset = page_size + sum((size + page_size - 1) // page_size * page_size
                                     for size in (kernel, ramdisk, second, recovery_dtbo))
        check(dtb_offset + dtb <= target.getinfo(entry).file_size, "Truncated boot image DTB")
        boot.seek(dtb_offset)
        check(boot.read(4) == b"\xd0\x0d\xfe\xed", "Boot image has an invalid DTB")
    dtbo = "IMAGES/dtbo.img"
    with target.open(dtbo) as image:
        check(target.getinfo(dtbo).file_size <= 8 * 1024 * 1024 and
              image.read(4) == b"\xd7\xb7\xab\x1e", "Invalid Coral DTBO image")
    for image in ("vbmeta", "vbmeta_system"):
        with target.open(f"IMAGES/{image}.img") as vbmeta:
            check(vbmeta.read(4) == b"AVB0", f"Invalid {image} image")


def verify(product_out, debug_adb):
    target_files = product_out / "obj/PACKAGING/target_files_intermediates/aospa_coral-target_files.zip"
    with ZipFile(target_files) as target:
        partitions = properties(target, "META/dynamic_partitions_info.txt")
        misc = properties(target, "META/misc_info.txt")
        timestamp = properties(target, "SYSTEM/build.prop")["ro.build.date.utc"]
        check(misc.get("ab_update") == "true", "Build must use A/B updates")
        check(partitions.get("virtual_ab") != "true", "Virtual A/B is enabled")
        check(partitions.get("super_partition_size") == "9755951104", "Unexpected Coral super size")
        check(partitions.get("super_google_dynamic_partitions_group_size") == str(SLOT_BYTES),
              "Unexpected Coral slot size")
        check(set(partitions.get("dynamic_partition_list", "").split()) ==
              set(DYNAMIC_PARTITIONS), "Unexpected dynamic partition list")
        check(int(misc.get("product_reserved_size") or 0) == 0,
              "Legacy /product reserve is enabled")
        sizes = {name: partition_image_size(target, name) for name in DYNAMIC_PARTITIONS}
        total = sum(sizes.values())
        check(total <= SLOT_BYTES, f"Images need {total:,} bytes, slot holds {SLOT_BYTES:,}: {sizes}")
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

        verify_boot_images(target)
        verify_keymaster(target)

    with ZipFile(product_out / "aospa_coral-ota.zip") as ota:
        metadata = properties(ota, "META-INF/com/android/metadata")
        check(metadata.get("ota-type") == "AB" and metadata.get("pre-device") == "coral",
              "OTA must target Coral and use A/B")
        check(metadata.get("post-timestamp") == timestamp, "OTA and target-files builds differ")
        check("pre-build" not in metadata, "OTA must have a full payload")
        with ota.open("payload.bin") as payload:
            header = payload.read(24)
            check(len(header) == 24 and header[:4] == b"CrAU", "Invalid OTA payload header")
            version, manifest_size, signature_size = struct.unpack_from(">QQI", header, 4)
            check(version == 2 and manifest_size > 0 and
                  24 + manifest_size + signature_size < ota.getinfo("payload.bin").file_size,
                  "Invalid OTA payload version or size")
    print(f"Coral dynamic images occupy {total:,} of {SLOT_BYTES:,} bytes in one slot")


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
