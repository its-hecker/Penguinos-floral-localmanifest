# PenguinOS Coral: isolated SELinux diagnostic (2026-11-21)

This is a **private, unverified userdebug diagnostic**, not a verified boot fix or a release branch.

## Scope

- Based on `debug/coral-reliable-logs-20261117`, retaining the fixed stock A/B partition sizes, vbmeta-system chain, early USB ADB and metadata boot capture.
- Pinned Coral device tree: `f74ad49c5cb2e2bee1f6c1e66c4d0bdd0e807f11`.
- Coral ONLY adds `BOARD_KERNEL_CMDLINE += androidboot.selinux=permissive` in `coral/BoardConfig.mk`.
- **FBE is unchanged**: `fileencryption=ice` and `keydirectory=/metadata/vold/metadata_encryption` remain in the `/data` fstab entry.
- Boot collector mounts metadata with `mount -t ext4 /dev/block/by-name/metadata /metadata` when recovery lacks fstab.

## Before new flashing or wiping

In root-capable recovery (Windows CMD):

```bat
adb root
adb shell "mkdir -p /metadata; grep -q ' /metadata ' /proc/mounts || mount -t ext4 /dev/block/by-name/metadata /metadata"
adb shell "ls -la /metadata/pixelos-boot-debug"
adb pull /metadata/pixelos-boot-debug penguin-boot-debug-before-test
```

If denied, try `adb shell setenforce 0` **in recovery** and retry. This does not change Android's SELinux mode.

## Build on ServerHive

```bash
set -eo pipefail
mkdir -p ~/penguinos-coral
cd ~/penguinos-coral
if [[ ! -d .repo ]]; then
  repo init -u https://github.com/Project-PenguinOS/manifest.git -b celerity --git-lfs
fi
manifest_url=https://github.com/its-hecker/Penguinos-floral-localmanifest.git
branch=debug/coral-selinux-isolation-20261121
if git -C .repo/local_manifests rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C .repo/local_manifests fetch "$manifest_url" "$branch"
  git -C .repo/local_manifests switch --detach FETCH_HEAD
elif [[ -e .repo/local_manifests ]]; then
  echo "Existing .repo/local_manifests is not a Git checkout; inspect before replacing" >&2
  exit 1
else
  git clone --branch "$branch" "$manifest_url" .repo/local_manifests
fi
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4
rm -rf out/target/product/coral/obj/PACKAGING/target_files_intermediates/aospa_coral-target_files
rm -f out/target/product/coral/aospa_coral-ota.zip
env -u PENGUIN_CORAL_ADB_PUBKEY OUT_DIR=out PENGUIN_DEV_USB_ADB=true \
  bash .repo/local_manifests/build.sh coral -t userdebug -i -l \
  2>&1 | tee ~/penguin-coral-selinux-isolation.log
python3 .repo/local_manifests/tools/verify_coral_boot.py out/target/product/coral --debug-adb
python3 - <<'PY'
from pathlib import Path
boot = Path("out/target/product/coral/boot.img").read_bytes()
assert b"androidboot.selinux=permissive" in boot[:4096], "Diagnostic cmdline missing from boot.img"
print("Verified: Coral boot.img includes androidboot.selinux=permissive")
PY
```

## Test

Use ONLY the full newly built OTA through PenguinOS recovery, without mixing boot/dtbo/vbmeta from another build. Inspect/update the target slot as appropriate for the device's A/B installation. If possible preserve the existing logs first. Do not reformat or erase metadata as a routine first step: this experiment deliberately changes only SELinux enforcement.

On Windows, download `tools/collect_penguin_boot.py` from this branch and run `py -3 collect_penguin_boot.py` before Android boot. Stop with Ctrl+C for the ZIP.

Interpretation: boots permissive -> inspect `avc: denied` and restore enforcing with targeted policy fixes; still fails -> investigate FBE/vold and first-stage failures with logs. A permissive build must NEVER be released or used for daily operation, and debug ADB currently trusts physically connected computers.
