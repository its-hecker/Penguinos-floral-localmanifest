#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -eo pipefail

device=${1:-}
case "$device" in
    coral|flame) shift ;;
    *) echo 'Usage: bash .repo/local_manifests/build.sh coral|flame [rom-build options]' >&2; exit 2 ;;
esac

if [[ ! -f "device/google/coral/aospa_$device.mk" || ! -f rom-build.sh ]]; then
    echo "Run repo sync with the $device manifest, then run this script from the ROM source root." >&2
    exit 1
fi

setup_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Fail fast if the pinned kernel compiler is missing. PenguinOS does not
# populate the LineageOS LLVM_AOSP_PREBUILTS_VERSION environment default.
kernel_clang_version=$(sed -nE 's/^[[:space:]]*TARGET_KERNEL_CLANG_VERSION[[:space:]]*:?=[[:space:]]*([^[:space:]#]+).*/\1/p' device/google/coral/BoardConfig-common.mk | head -n 1)
kernel_clang="prebuilts/clang/host/linux-x86/clang-${kernel_clang_version}/bin/clang"
if [[ -z "$kernel_clang_version" || ! -x "$kernel_clang" ]] || ! "$kernel_clang" --version >/dev/null 2>&1; then
    echo "Floral kernel Clang prebuilt missing or unusable: $kernel_clang" >&2
    echo "Sync prebuilts/clang/host/linux-x86 or verify TARGET_KERNEL_CLANG_VERSION." >&2
    exit 1
fi

git -C "vendor/google/$device" lfs pull
git -C kernel/google/msm-4.14 submodule update --init --recursive
python3 "$setup_dir/tools/prepare.py" "$device"
# Kernel headers_install is required for qti_kernel_headers when Soong only
# has the generator dummy dependency. Verify the real headers before compiling.
if [[ "$device" == "coral" ]]; then
    python3 "$setup_dir/tools/kernel_uapi.py"
fi

exec bash ./rom-build.sh "$device" "$@"
