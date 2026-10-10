#!/system/bin/sh
# Run on Android through adb shell. One hour maximum, four ~1 MiB log files.
# Only USB/JetLink tags are recorded. Existing files are retained and rotated.
set -eu
out=/sdcard/Download/ClarityPilot-usb-test
pidfile=/data/local/tmp/clarity-pixel-usb-log.pid
if [ -f "$pidfile" ]; then
  old=$(cat "$pidfile")
  case "$old" in
    ''|*[!0-9]*) ;;
    *) if [ -r "/proc/$old/cmdline" ] && tr '\000' ' ' < "/proc/$old/cmdline" | grep -q "logcat.*$out/usb.log"; then
         echo "USB capture already running: $old"
         exit 0
       fi ;;
  esac
fi
mkdir -p "$out"
nohup timeout 3600 logcat -b main -b system -b crash \
  -v threadtime -T 1 -f "$out/usb.log" -r 1024 -n 3 \
  'jetlink:V' 'Jetlink:V' 'JetLink:V' 'litert:W' \
  'UsbHostManager:V' 'UsbPortManager:V' 'UsbDeviceManager:V' \
  'UsbService:V' 'UsbAlsaManager:V' '*:S' > "$out/capture-status.txt" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$pidfile"
echo "USB capture started: $pid; capped near 4 MiB; expires after one hour"
