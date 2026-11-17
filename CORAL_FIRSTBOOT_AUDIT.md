# PenguinOS Celerity / coral first-boot source audit (2026-11-17)

This is a **candidate fix** and a clean rebuild recipe, not a claim of verified
successful startup. The reported phone repeatedly returns to recovery before
USB ADB becomes available. All captured dmesg output is from **recovery**,
so there is no confirmed Android boot panic or init error.

## Examined / disposition

- Device: `its-hecker/penguinos-floral-dt`, pinned to
  `c51170ffdc433bb468463615b6207d3820f86a80`.
- Kernel: `its-hecker/infinity_cnb_kernel_google_msm-4.14`,
  `aaaa03e40200825133d21402cad8f2a86939a778`, shared
  with the already working Infinity-X/Coral configuration. Not modified.
- Vendor: `its-hecker/pixelos_proprietary_vendor_google_coral`
  `0684137113420155d238424f1695a2393ae3143d`;
  retained; contains the reviewed atcmdfwd ownership correction.
- Product & first-stage ramdisk: `BOARD_AVB_VBMETA_SYSTEM` includes
  `system`, `system_ext`, `product`, but fstab previously used the
  bare `avb` flag for product. The device tree now uses
  `avb=vbmeta_system` for product to match the chain owner.
- Existing stock A/B branch fixes the super size to 9,755,951,104 bytes
  and disables Virtual A/B (unsupported userspace snapshots on this kernel).
  This branch inherits those fixes.
- Existing diagnostic branch fixes the USB configfs state to 1 and installs
  crash-loop hold and bounded metadata boot capture. Inherits those changes.
- Verifier now checks chained AVB mapping in the **packaged boot ramdisk**,
  along with size, A/B OTA payload and other boot checks.

## ServerHive rebuild from the existing checkout

```bash
set -eo pipefail
cd ~/penguinos-coral
git -C .repo/local_manifests fetch \
  https://github.com/its-hecker/Penguinos-floral-localmanifest.git \
  fix/coral-firstboot-audit-20261117
git -C .repo/local_manifests switch --detach FETCH_HEAD
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4

# Discard stale packaged images/OTA metadata; retain compilation cache.
rm -rf out/target/product/coral/obj/PACKAGING/target_files_intermediates/aospa_coral-target_files
rm -f out/target/product/coral/aospa_coral-ota.zip
env -u PENGUIN_CORAL_ADB_PUBKEY OUT_DIR=out PENGUIN_DEV_USB_ADB=true \
    bash .repo/local_manifests/build.sh coral -t userdebug -i -l \
    2>&1 | tee ~/penguin-coral-firstboot-audit.log

python3 .repo/local_manifests/tools/verify_coral_boot.py \
  out/target/product/coral --debug-adb
```

Do not mix a boot image, dtbo, vbmeta, or OTA zip from different builds or
slots. Use the newly generated full OTA through the recovery intended for
this device, and verify the installed active slot. Leave user data intact
when diagnosing; a factory reset is not evidence of a source fix.

If it still returns to recovery, retrieve pstore and the bounded
`/metadata/pixelos-boot-debug` record in *root-capable* recovery. A recovery
dmesg does not prove the failed Android mount stage.

**Security:** This temporary build trusts USB-connected computers and disables
some crash-loop safety actions for diagnosis. Never distribute it as a release.
