# PenguinOS Coral: temporary logo-stage ADB diagnostic

Branch: `debug/coral-logo-adb-20261117` (based on `fix/coral-stock-ab-20261117`).

**Not a boot fix.** This is an *isolated* test configuration designed to keep
Android accessible over USB during some userspace crash loops. It does not
prevent kernel panics, fatal first-stage mount problems, bootloader retry
exhaustion, or hard watchdog resets.

## What changed

- The pinned Coral device tree uses `sys.usb.configfs=1`, matching
  `system/core/rootdir/init.usb.configfs.rc`. The old code set `2`,
  which did not satisfy the system ADB binding conditions.
- Native ADB is requested after the vendor partition is available, again when
  the vendor diagnostic property is loaded, and once APEX is activated.
- The `userdebug`-only startup file `penguin-bootloop-hold.rc` sets
  `init.svc_debug.no_fatal.<service>` for known critical native services.
  The pinned PenguinOS init honors these properties before deliberately
  aborting init after repeated critical-service exits.
- The test build also sets `persist.sys.disable_rescue=true` after /data
  is mounted, to avoid Rescue Party recovery during crash-loop analysis.
- The verifier now checks that the diagnostic RC files are actually packaged.

## Build (ServerHive)

```bash
cd ~/penguinos-coral
git -C .repo/local_manifests fetch \
  https://github.com/its-hecker/Penguinos-floral-localmanifest.git \
  debug/coral-logo-adb-20261117
git -C .repo/local_manifests switch --detach FETCH_HEAD
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4

env -u PENGUIN_CORAL_ADB_PUBKEY \
  OUT_DIR=out PENGUIN_DEV_USB_ADB=true \
  bash .repo/local_manifests/build.sh coral -t userdebug -i -l \
  2>&1 | tee ~/penguin-coral-logo-adb.log

python3 .repo/local_manifests/tools/verify_coral_boot.py \
  out/target/product/coral --debug-adb
```

On the computer connected by USB, run `adb wait-for-device` before
booting the test image. When `adb devices` says `device` (not `recovery`),
capture `adb logcat -b all -v threadtime`; if a root shell is available,
also capture `adb shell dmesg`.

## Security and cleanup

The `PENGUIN_DEV_USB_ADB=true` test mode sets `ro.adb.secure=0`,
so **any physically connected computer** can use USB ADB without an RSA
authorization prompt. Only use this build on a physically controlled
personal test device. **Do not distribute or use for everyday operation.**
When leaving the diagnostic build, restore the stable ROM with
`PENGUIN_DEV_USB_ADB=false`, and ensure
`persist.sys.disable_rescue` is reset to `false` on the installed system.

No changes were made to stable Coral, Flame, the kernel, vendor repository,
or FaceID/MotionSense plugin source repositories.
