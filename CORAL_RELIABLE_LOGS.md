# PenguinOS Coral diagnostic bootlog build (2026-11-17)

Branch: debug/coral-reliable-logs-20261117
Base: fix/coral-firstboot-audit-20261117

This is a PRIVATE userdebug diagnostic build, not a verified boot fix.
It keeps Coral's stock super geometry, regular A/B layout, product AVB
mapping, and audited vendor/kernel/FaceID/Motion Sense pins.

## What this build captures

1. USB ADB starts as early as the second-stage init and ADB APEX allow.
   This test build automatically requests root adbd and skips USB PC
   authorization. Android Settings and SystemUI are not required.
2. A capped boot-capture service saves logcat, dmesg, properties, processes,
   mount table, status and command line in /metadata/pixelos-boot-debug.
   It keeps one older capture as previous-* files, even across quick reboots.
3. Second-stage init writes PENGUIN_BOOT_STAGE markers to /dev/kmsg so
   the kernel console/pstore can distinguish how far boot progressed.
4. A cross-platform Python collector watches Android and recovery ADB.
   When recovery appears, it pulls /metadata/pixelos-boot-debug,
   /sys/fs/pstore, and RECOVERY dmesg clearly labeled as such.

IMPORTANT LIMIT: ADB cannot operate until first-stage partitions mount and
the adbd APEX is usable. The Floral kernel supports PSTORE_CONSOLE and
PSTORE_RAM, but a warm-reset record is not guaranteed. If Android fails at
first-stage mounting, AVB, or an early watchdog, no Android-side ADB log
may be possible. A recovery dmesg is not a failed-Android dmesg.

## ServerHive from mkdir (existing or fresh tree)

    set -eo pipefail
    mkdir -p ~/penguinos-coral
    cd ~/penguinos-coral

    if [[ ! -d .repo ]]; then
      repo init -u https://github.com/Project-PenguinOS/manifest.git \
        -b celerity --git-lfs
    fi

    repo_url=https://github.com/its-hecker/Penguinos-floral-localmanifest.git
    branch=debug/coral-reliable-logs-20261117

    if [[ -d .repo/local_manifests/.git ]]; then
      git -C .repo/local_manifests fetch "$repo_url" "$branch"
      git -C .repo/local_manifests switch --detach FETCH_HEAD
    elif [[ -e .repo/local_manifests ]]; then
      echo "Existing local manifests are not a Git clone; inspect them." >&2
      exit 1
    else
      git clone -b "$branch" "$repo_url" .repo/local_manifests
    fi

    repo sync -c --fail-fast --no-clone-bundle --no-tags -j4

    rm -rf out/target/product/coral/obj/PACKAGING/target_files_intermediates/aospa_coral-target_files
    rm -f out/target/product/coral/aospa_coral-ota.zip

    env -u PENGUIN_CORAL_ADB_PUBKEY \
      OUT_DIR=out PENGUIN_DEV_USB_ADB=true \
      bash .repo/local_manifests/build.sh coral -t userdebug -i -l \
      2>&1 | tee ~/penguin-coral-reliable-logs.log

    python3 .repo/local_manifests/tools/verify_coral_boot.py \
      out/target/product/coral --debug-adb

    echo 'ROM: out/target/product/coral/aospa_coral-ota.zip'

Never mix boot, dtbo, vbmeta or OTA from different builds or slots.

## Collect on a PC (start BEFORE booting the phone)

Requires Android platform-tools and Python 3, with USB data cable attached.

macOS/Linux:

    curl -fL -o collect_penguin_boot.py \
      https://raw.githubusercontent.com/its-hecker/Penguinos-floral-localmanifest/debug/coral-reliable-logs-20261117/tools/collect_penguin_boot.py
    python3 collect_penguin_boot.py

Windows PowerShell:

    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/its-hecker/Penguinos-floral-localmanifest/debug/coral-reliable-logs-20261117/tools/collect_penguin_boot.py" -OutFile collect_penguin_boot.py
    py -3 .\collect_penguin_boot.py

If adb is not on PATH, use --adb followed by its executable path.
The collector does not reboot, flash, or wipe the phone. Start it before
the attempted boot; if Android ADB never appears, wait for recovery.
Press Ctrl+C to get a timestamped ZIP; send that ZIP.

Security: ro.adb.secure=0 and root ADB trust ANY physically connected
computer. Do not distribute or use this temporary test build daily.
Switch back to a stable source and remove the development ADB mode later.
