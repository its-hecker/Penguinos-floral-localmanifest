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
git -C "vendor/google/$device" lfs pull
git -C kernel/google/msm-4.14 submodule update --init --recursive
python3 "$setup_dir/tools/prepare.py" "$device"

exec bash ./rom-build.sh "$device" "$@"
