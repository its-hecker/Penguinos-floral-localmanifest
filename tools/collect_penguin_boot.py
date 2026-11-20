#!/usr/bin/env python3
"""PenguinOS coral bootloop recorder (Python 3, Windows/macOS/Linux).

Run BEFORE rebooting/booting the phone, with Android platform-tools installed:
  python3 collect_penguin_boot.py
  py -3 collect_penguin_boot.py     # Windows

Captures live Android ADB when it appears, then captures persisted diagnostic
files and pstore from recovery even if Android ADB never appeared. Does not
reboot, unlock, wipe, or flash the phone. Stop with Ctrl+C to create a ZIP.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import shutil
import subprocess
import sys
import time


def execute(argv, timeout=7):
    try:
        return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(argv, -1, b"", str(error).encode())


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def write_result(path, result):
    if result.stdout:
        path.write_bytes(result.stdout)
    elif path.exists():
        path.unlink()
    if result.stderr:
        path.with_suffix(path.suffix + ".stderr.txt").write_bytes(result.stderr)


def get_connected(adb, specified):
    result = execute([adb, "devices"], timeout=4)
    if result.returncode != 0:
        return None, None
    for line in result.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 2 and (not specified or cols[0] == specified):
            if cols[1] in ("device", "recovery", "unauthorized", "offline", "sideload"):
                return cols[0], cols[1]
    return None, None


def capture(adb, serial, folder, state):
    folder.mkdir(parents=True, exist_ok=True)
    prefix = [adb, "-s", serial]
    def shell(filename, command):
        output = execute(prefix + ["shell", command], timeout=8)
        write_result(folder / filename, output)

    print(f"\n[{stamp()}] {state} ADB: capturing information in {folder}", flush=True)
    shell("properties.txt", "getprop")
    shell("kernel-current.txt" if state == "device" else "RECOVERY-kernel.txt", "dmesg")
    shell("mounts.txt", "cat /proc/mounts")
    shell("cmdline.txt", "cat /proc/cmdline")
    shell("pstore-list.txt", "ls -la /sys/fs/pstore")
    shell("boot-id.txt", "cat /proc/sys/kernel/random/boot_id")
    if state == "device":
        shell("processes.txt", "ps -A")
        output = execute(prefix + ["logcat", "-b", "all", "-v", "threadtime", "-d"], timeout=8)
        write_result(folder / "logcat-snapshot.txt", output)
    else:
        # Recovery may not have /etc/fstab; do not use bare "mount /metadata".
        # Explicit ext4 mount preserves existing evidence and does not wipe it.
        shell("recovery-identity.txt", "id")
        mounted = execute(prefix + ["shell", "grep -q ' /metadata ' /proc/mounts"], timeout=8)
        if mounted.returncode != 0:
            mount = execute(prefix + ["shell",
                             "mkdir -p /metadata && mount -t ext4 /dev/block/by-name/metadata /metadata"],
                            timeout=8)
            (folder / "metadata-mount-attempt.txt").write_text(
                "returncode=" + str(mount.returncode) + "\n"
                + mount.stdout.decode(errors="replace")
                + mount.stderr.decode(errors="replace"),
                encoding="utf-8",
            )
        shell("metadata-mount.txt", "grep ' /metadata ' /proc/mounts || echo metadata-not-mounted")
        shell("boot-debug-list.txt", "ls -la /metadata/pixelos-boot-debug")
        for remote, local in (
            ("/metadata/pixelos-boot-debug", "saved-android-boot"),
            ("/sys/fs/pstore", "pstore"),
        ):
            dst = folder / local
            dst.mkdir(parents=True, exist_ok=True)
            output = execute(prefix + ["pull", remote, str(dst)], timeout=20)
            if output.returncode != 0:
                (folder / (local + "-pull-status.txt")).write_text(
                    output.stdout.decode(errors="replace") + output.stderr.decode(errors="replace"),
                    encoding="utf-8",
                )
        shell("recovery-log.txt", "cat /tmp/recovery.log")
        shell("last-kmsg.txt", "cat /proc/last_kmsg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb", help="Path to platform-tools adb executable")
    parser.add_argument("--serial", help="Device serial if multiple ADB devices are connected")
    parser.add_argument("--output", default="penguin-bootlogs-" + stamp())
    args = parser.parse_args()
    folder = pathlib.Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    adb = args.adb
    if execute([adb, "version"], timeout=5).returncode:
        sys.exit("ADB not found. Install Android platform-tools or use --adb PATH_TO_ADB.")

    print("Connect Coral with a USB data cable, THEN reboot/install the diagnostic ROM.", flush=True)
    print("Watching Android AND recovery; Ctrl+C saves a ZIP. Never flashes or reboots.", flush=True)
    current = None
    recovery_done = set()
    stream = None
    livefile = None
    logcat_path = None
    try:
        while True:
            serial, state = get_connected(adb, args.serial)
            mode = (serial, state)
            if mode != current:
                if stream:
                    stream.terminate()
                    try:
                        stream.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        stream.kill()
                    stream = None
                if livefile:
                    livefile.close()
                    livefile = None
                if logcat_path and logcat_path.exists() and logcat_path.stat().st_size == 0:
                    logcat_path.unlink()
                if serial:
                    print(f"[{stamp()}] {serial}: {state}", flush=True)
                current = mode
                if serial and state == "device":
                    attempt = folder / ("android-" + stamp())
                    attempt.mkdir(parents=True, exist_ok=True)
                    # Start live streaming FIRST; adb may vanish during the snapshots.
                    logcat_path = attempt / "logcat-live.txt"
                    livefile = logcat_path.open("wb")
                    stream = subprocess.Popen([adb, "-s", serial, "logcat", "-b", "all",
                                               "-v", "threadtime"], stdout=livefile,
                                              stderr=subprocess.DEVNULL)
                    capture(adb, serial, attempt, state)
                elif serial and state == "recovery":
                    key = (serial, stamp())
                    if key not in recovery_done:
                        recovery_done.add(key)
                        capture(adb, serial, folder / ("recovery-" + stamp()), state)
            if stream and stream.poll() is not None:
                stream = None
                if livefile:
                    livefile.close()
                    livefile = None
                # ADB may disconnect briefly while Android bootloops.
            if state == "device" and stream is None and livefile is None and logcat_path:
                livefile = logcat_path.open("ab")
                stream = subprocess.Popen([adb, "-s", serial, "logcat", "-b", "all",
                                           "-v", "threadtime"], stdout=livefile,
                                          stderr=subprocess.DEVNULL)
            time.sleep(0.45)
    except KeyboardInterrupt:
        print("\nStopping capture...", flush=True)
    finally:
        if stream:
            stream.terminate()
            try:
                stream.wait(timeout=2)
            except subprocess.TimeoutExpired:
                stream.kill()
        if livefile:
            livefile.close()
        if logcat_path and logcat_path.exists() and logcat_path.stat().st_size == 0:
            logcat_path.unlink()
        archive = shutil.make_archive(str(folder), "zip", root_dir=folder)
        print(f"Send this ZIP: {archive}", flush=True)


if __name__ == "__main__":
    main()
