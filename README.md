# PenguinOS for Pixel 4 XL (coral)

This is the Android 17 `celerity` build configuration for `coral`.
It uses the PixelOS device tree and vendor, the Floral 4.14 KernelSU Next
kernel, Lunaris Dolby, hardware 3D Face ID, Motion Sense, Active Edge, and
the signed Google Camera split set.

The first compile and phone validation are pending. The pinned device-tree
commit must be present on the `main` branch of
[penguinos-floral-dt](https://github.com/its-hecker/penguinos-floral-dt)
before the initial sync.

From a fresh ServerHive checkout:

```bash
mkdir -p ~/penguinos-coral
cd ~/penguinos-coral
repo init -u https://github.com/Project-PenguinOS/manifest.git -b celerity --git-lfs
git clone -b main https://github.com/its-hecker/Penguinos-floral-localmanifest.git .repo/local_manifests
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4
bash .repo/local_manifests/build.sh coral -g
```

The build helper runs the hardware preparation before invoking PenguinOS's
build script. Use `-l` to select the upstream vanilla build option.

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
git -C .repo/local_manifests pull --ff-only origin main
bash .repo/local_manifests/build.sh coral -g
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
