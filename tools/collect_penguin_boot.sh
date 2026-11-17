#!/usr/bin/env bash
# PenguinOS Coral boot-failure logger for macOS or Linux.
# Requirements: Android platform-tools (adb), USB data cable.
# Usage: bash collect_penguin_boot.sh
# Optional: ADB=/full/path/to/adb bash collect_penguin_boot.sh
set -u

adb_bin=adb
if [[ -n "$(printenv ADB 2>/dev/null)" ]]; then adb_bin="$(printenv ADB)"; fi
if ! command -v "$adb_bin" >/dev/null 2>&1; then
  echo "ADB not found. Install Android platform-tools or set ADB=/path/to/adb" >&2
  exit 1
fi

out="$PWD/penguin-logs-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
logpid=""
last=""

stop_logcat() {
  if [[ -n "$logpid" ]]; then
    kill "$logpid" 2>/dev/null || :
    wait "$logpid" 2>/dev/null || :
    logpid=""
  fi
}
finish() {
  stop_logcat
  if command -v zip >/dev/null 2>&1; then
    (cd "$(dirname "$out")" && zip -rq "$(basename "$out").zip" "$(basename "$out")")
    echo "SEND THIS ZIP: $out.zip"
  else
    echo "ZIP unavailable; send this folder: $out"
  fi
}
trap finish EXIT
trap 'exit 0' INT TERM

save_shell() {
  local serial="$1" file="$2" cmd="$3"
  "$adb_bin" -s "$serial" shell "$cmd" > "$file" 2> "$file.stderr.txt" || :
}

capture_android() {
  local serial="$1"
  local dir="$out/android-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dir"
  echo "[Android] LIVE logcat streaming to $dir/logcat-live.txt"
  # Start the live stream first so short boot attempts are not missed.
  "$adb_bin" -s "$serial" logcat -b all -v threadtime \
    > "$dir/logcat-live.txt" 2> "$dir/logcat-errors.txt" &
  logpid=$!
  save_shell "$serial" "$dir/properties.txt" "getprop"
  save_shell "$serial" "$dir/kernel-android.txt" "dmesg"
  save_shell "$serial" "$dir/cmdline.txt" "cat /proc/cmdline"
  save_shell "$serial" "$dir/mounts.txt" "cat /proc/mounts"
}

capture_recovery() {
  local serial="$1"
  local dir="$out/recovery-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dir"
  echo "[Recovery] Pulling saved Android boot capture and pstore to $dir"
  save_shell "$serial" "$dir/RECOVERY-kernel.txt" "dmesg"
  save_shell "$serial" "$dir/RECOVERY-properties.txt" "getprop"
  save_shell "$serial" "$dir/RECOVERY-mounts.txt" "cat /proc/mounts"
  save_shell "$serial" "$dir/pstore-list.txt" "ls -la /sys/fs/pstore"
  save_shell "$serial" "$dir/recovery-log.txt" "cat /tmp/recovery.log"
  "$adb_bin" -s "$serial" shell "mount /metadata" > "$dir/metadata-mount.txt" 2>&1 || :
  "$adb_bin" -s "$serial" pull /metadata/pixelos-boot-debug "$dir/saved-android-boot" \
    > "$dir/saved-android-boot-pull.txt" 2>&1 || :
  "$adb_bin" -s "$serial" pull /sys/fs/pstore "$dir/pstore" \
    > "$dir/pstore-pull.txt" 2>&1 || :
}

echo "Connect phone with a USB data cable. Start BEFORE booting the diagnostic ROM."
echo "Watching for both Android and recovery ADB. Press Ctrl+C to save a ZIP."
while :; do
  row=$("$adb_bin" devices 2>/dev/null | awk 'NR > 1 && ($2 == "device" || $2 == "recovery") { print $1, $2; exit }')
  serial=""
  state=""
  if [[ -n "$row" ]]; then read -r serial state <<< "$row"; fi
  current="$serial|$state"
  if [[ "$current" != "$last" ]]; then
    stop_logcat
    if [[ -n "$state" ]]; then
      echo "[$(date +%H:%M:%S)] $serial $state"
      if [[ "$state" == "device" ]]; then capture_android "$serial"; fi
      if [[ "$state" == "recovery" ]]; then capture_recovery "$serial"; fi
    fi
    last="$current"
  fi
  sleep 0.5
done
