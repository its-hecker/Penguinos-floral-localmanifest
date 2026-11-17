# PenguinOS for Pixel 4 XL (coral)

This is the Android 17 `celerity` build configuration for `coral`.
It uses the PixelOS device tree and vendor, the Floral 4.14 KernelSU Next
kernel, Lunaris Dolby, hardware 3D Face ID, Motion Sense, Active Edge, and
the signed Google Camera split set.

This branch uses Coral's stock 9,755,951,104-byte `super` geometry and regular
A/B updates. Celerity requires userspace snapshots for Virtual A/B. The
Floral kernel supports kernel snapshots. The first boot test builds the vanilla
product to fit the stock slot and retains the Floral device integrations.
Coral uses default ext4 sizing and skips the PixelOS space reserve for
separately installed Google Apps. The manifest pins the Celerity init, mount,
SELinux, BPF, recovery and OTA sources together with the device, vendor and kernel.

From a fresh ServerHive checkout:

```bash
mkdir -p ~/penguinos-coral
cd ~/penguinos-coral
repo init -u https://github.com/Project-PenguinOS/manifest.git -b celerity --git-lfs
git clone -b fix/coral-stock-ab-20261117 https://github.com/its-hecker/Penguinos-floral-localmanifest.git .repo/local_manifests
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4
```

### Coral boot diagnostics

The private Coral `userdebug` build accepts ADB from any connected USB
computer without an authorization prompt, as in HeckerOS. The USB gadget
starts at `early-fs`, and init queues adbd until APEX configuration is ready.
`adb root` requests a root shell and `adb logcat -b all` captures the boot log.

```bash
env -u PENGUIN_CORAL_ADB_PUBKEY OUT_DIR=out PENGUIN_DEV_USB_ADB=true \
  bash .repo/local_manifests/build.sh coral -t userdebug -i -l

product_out=out/target/product/coral
python3 .repo/local_manifests/tools/verify_coral_boot.py "$product_out" --debug-adb
unzip -oj "$product_out/obj/PACKAGING/target_files_intermediates/aospa_coral-target_files.zip" \
  IMAGES/boot.img IMAGES/dtbo.img IMAGES/vbmeta.img -d "$product_out/install"
```

Use the images in `out/target/product/coral/install` and sideload
`out/target/product/coral/aospa_coral-ota.zip` through the PenguinOS recovery
from that build. The verification step checks the unpacked sizes of the four
logical partition images, the boot and DTBO structure, the Citadel Keymaster
binaries and their crypto library, and the first-stage fstab and OTA metadata.
System startup still needs a phone test. Recovery ADB can read diagnostic files
from `/metadata/pixelos-boot-debug` after mounting Metadata if Android init
reaches the capture service.

### Qualcomm firmware mountpoint make-rule compatibility

The preparation step automatically reconciles duplicate directory creation
recipes between Qualcomm's `AndroidBoardCommon.mk` and PenguinOS's
`vendor/aospa/build/core/mkdir.mk`. This handles `firmware_mnt`,
`soccp_firmware`, `bt_firmware`, `dsp`, and the root `persist` symlink,
plus other mount targets actually owned by synced Qualcomm rules. It does not
disable Qualcomm's firmware mountpoints or modify runtime fstab configuration.

The same preparation step also guards Qualcomm's explicit root `/persist`
rule when the Floral board configuration already provides
`/mnt/vendor/persist:/persist` through PenguinOS's rootdir symlink rules.
This prevents duplicate Ninja outputs without removing the runtime symlink.

It is safe to rerun and also replaces an earlier local-only three-directory
workaround. After updating the local manifest, simply run the normal build
helper again; no clean build is required solely for this make-rule fix.

```bash
cd ~/penguinos-coral
bash .repo/local_manifests/build.sh coral -l
```

### Coral Qualcomm display kernel UAPI headers

`build.sh coral` now invokes `tools/kernel_uapi.py` after the usual source
preparation and before `rom-build.sh`. This runs the Floral kernel's
`headers_install` target into the same
`out/soong/.intermediates/vendor/hecker/floral/kernel-build/build/soong/generated_kernel_includes/gen`
path consumed by `qti_kernel_headers` in the SM8150 display modules.

It verifies `usr/include/drm/sde_drm.h`,
`usr/include/drm/msm_drm_pp.h`, and
`usr/include/media/msm_media_info.h`; the build stops immediately if
installation silently leaves them missing despite the Soong `.dummy_dep`.
It then runs the existing `vendor/hecker/floral/kernel-build/tools/clean_headers.sh`
Bionic cleanup to rename the kernel's `struct sigaction` to
`struct __kernel_sigaction` in generated signal headers, avoiding the
Bionic duplicate-type error while preserving the kernel ABI.

No full source resync or clean build is needed solely for this workaround.
The ROM build still needs to be confirmed on ServerHive.

### Knowles Athletico sound-trigger UAPI headers (Coral)

The `hardware/knowles/athletico/sound_trigger_hal` module uses kernel
UAPI definitions from `linux/mfd/adnc/` (including `iaxxx-odsp.h` and
`iaxxx-system-identifiers.h`). The upstream HAL only lists
`device_kernel_headers`. The Coral preparation step applies
`patches/knowles-generated-kernel-headers.patch`, adding
`generated_kernel_headers` to its existing Soong defaults. This provides
access to the sanitized Floral UAPI headers already installed and checked
by `tools/kernel_uapi.py` without copying raw headers or disabling
Knowles sound-trigger components.

This compatibility patch is automatically applied on Coral builds.
