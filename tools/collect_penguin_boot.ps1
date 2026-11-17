# PenguinOS Coral boot-failure ADB collector
# Windows PowerShell 5.1+; only Android platform-tools/adb required.
# Run BEFORE booting the phone:
# powershell -NoProfile -ExecutionPolicy Bypass -File .\collect_penguin_boot.ps1
param([string]$Adb = "adb")

$ErrorActionPreference = "Continue"
try {
    & $Adb version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "adb exited with code $LASTEXITCODE" }
} catch {
    Write-Host "ADB missing. Install Android platform-tools, add adb.exe to PATH, or use -Adb 'C:\path\adb.exe'." -ForegroundColor Red
    exit 1
}

$folder = Join-Path (Get-Location).Path ("penguin-logs-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$script:stream = $null

function Stop-LogStream {
    if ($script:stream) {
        try {
            if (-not $script:stream.HasExited) {
                $script:stream.Kill()
                $script:stream.WaitForExit(1500) | Out-Null
            }
        } catch {}
        $script:stream = $null
    }
}

function Save-Shell([string]$serial, [string]$file, [string]$command) {
    try {
        & $Adb -s $serial shell $command 2>&1 | Out-File -FilePath $file -Encoding utf8
    } catch {
        [string]$_ | Out-File -FilePath ($file + ".error.txt")
    }
}

function Capture-Device([string]$serial) {
    $where = Join-Path $folder ("android-" + (Get-Date -Format "yyyyMMdd-HHmmssfff"))
    New-Item -ItemType Directory -Path $where -Force | Out-Null
    Write-Host "[Android] Starting LIVE logcat: $where"
    try {
        $script:stream = Start-Process -FilePath $Adb -ArgumentList @("-s", $serial, "logcat", "-b", "all", "-v", "threadtime") -RedirectStandardOutput (Join-Path $where "logcat-live.txt") -RedirectStandardError (Join-Path $where "logcat-errors.txt") -PassThru -WindowStyle Hidden
    } catch {
        Write-Host "Failed to start live logcat: $_"
    }
    Save-Shell $serial (Join-Path $where "properties.txt") "getprop"
    Save-Shell $serial (Join-Path $where "kernel-android.txt") "dmesg"
    Save-Shell $serial (Join-Path $where "cmdline.txt") "cat /proc/cmdline"
    Save-Shell $serial (Join-Path $where "mounts.txt") "cat /proc/mounts"
}

function Capture-Recovery([string]$serial) {
    $where = Join-Path $folder ("recovery-" + (Get-Date -Format "yyyyMMdd-HHmmssfff"))
    New-Item -ItemType Directory -Path $where -Force | Out-Null
    Write-Host "[Recovery] Pulling saved Android capture and pstore into $where"
    Save-Shell $serial (Join-Path $where "RECOVERY-kernel.txt") "dmesg"
    Save-Shell $serial (Join-Path $where "RECOVERY-properties.txt") "getprop"
    Save-Shell $serial (Join-Path $where "RECOVERY-mounts.txt") "cat /proc/mounts"
    Save-Shell $serial (Join-Path $where "pstore-list.txt") "ls -la /sys/fs/pstore"
    Save-Shell $serial (Join-Path $where "recovery-log.txt") "cat /tmp/recovery.log"
    # Some recoveries already mount Metadata, others need an explicit mount.
    & $Adb -s $serial shell "mount /metadata" 2>&1 | Out-File (Join-Path $where "metadata-mount.txt") -Encoding utf8
    & $Adb -s $serial pull "/metadata/pixelos-boot-debug" (Join-Path $where "saved-android-boot") 2>&1 | Out-File (Join-Path $where "saved-android-boot-pull.txt") -Encoding utf8
    & $Adb -s $serial pull "/sys/fs/pstore" (Join-Path $where "pstore") 2>&1 | Out-File (Join-Path $where "pstore-pull.txt") -Encoding utf8
}

Write-Host "Connect phone via USB data cable; boot the diagnostic ROM."
Write-Host "Watching for Android and recovery. Press Ctrl+C to save a ZIP."
$last = ""
try {
    while ($true) {
        $serial = ""
        $mode = ""
        foreach ($line in @(& $Adb devices 2>$null)) {
            if ($line -match '^\s*(\S+)\s+(device|recovery)\s*$') {
                $serial = $Matches[1]
                $mode = $Matches[2]
                break
            }
        }
        $current = "$serial|$mode"
        if ($current -ne $last) {
            Stop-LogStream
            if ($mode) {
                Write-Host ("[{0}] {1}: {2}" -f (Get-Date -Format "HH:mm:ss"), $serial, $mode)
                if ($mode -eq "device") { Capture-Device $serial }
                if ($mode -eq "recovery") { Capture-Recovery $serial }
            }
            $last = $current
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    Stop-LogStream
    $zip = $folder + ".zip"
    try {
        Compress-Archive -Path (Join-Path $folder "*") -DestinationPath $zip -Force
        Write-Host "SEND THIS ZIP: $zip" -ForegroundColor Green
    } catch {
        Write-Host "Archive failed; send the captured folder: $folder"
    }
}
