# Pixel USB recovery preparation — October 10, 2026

The Pixel now has **JetLink 0.8.5-clarity-tensor.6**, and the comma has a tested USB transport recovery patch. These changes address receive-buffer starvation and a stale reconnect attempt. **The physical USB resets from the drive are not yet proven fixed.** The next check is stationary with the Android Auto adapter unplugged, followed by log review before another driving test.

## What the evidence supports

The preceding Pixel drive contained repeated large-model fallback and USB errors. Comma kernel records show disconnect/reconfigure cycles near +36, +149 and +418 seconds, returning at SuperSpeed. There was no corresponding Type-C detach until the final unplug. This supports real USB bus/controller resets, but does not identify a cable, power supply, controller or software root cause.

The Android Auto adapter was plugged into the car separately; the Pixel connected to it wirelessly. It therefore did not share the Pixel-to-comma USB hub. Removing it eliminates the phone's wireless Android Auto workload for comparison. The user's approximate halfway removal time is insufficient to establish causation. Detailed route logs remain private.

## Changes installed

1. **Pixel USB receive reserve:** repost consumed receive buffers immediately after copying a message, before inference starts. A regression reproduces a 400 KiB message leaving only 112 KiB queued for the next request, stalling its remaining 288 KiB. The repaired path restores the existing 512 KiB receive reserve without increasing buffer depth. Four successive payloads retain byte order and transfer without a new application read.
2. **Pixel connection wake lock:** retain the foreground service's partial wake lock while the USB device is attached, including the handshake/rejoin gap. Release it on detach or service destruction. Thermal limits and CPU frequency policy are unchanged.
3. **Comma reconnect:** inspect already-completed asynchronous writes and reader errors before reusing an apparently live transport. If a USB reset completed a queued LEAVE with endpoint shutdown, discard that client before another HELLO. Ordinary pending writes remain valid; this check does not wait for USB or run in the inference frame loop.
4. **USB diagnostics:** Pixel errors now include numeric completion status and actual/requested transfer lengths.

Protocol v3, the normal Tensor handshake, Cinque Terre V2, precompiled Tensor G6 execution, warmup, frame deadlines, fallback and thermal protections remain in place. No vehicle-control tuning changed. The temporary desk TCP listener was disabled after validation.

## Installed versions and reproducibility

| Component | Identity |
| --- | --- |
| Pixel APK | `0.8.5-clarity-tensor.6`, version code `80506` |
| APK SHA-256 | `e17bdb13f6f9748825837b3ce376194887a15145ca7c238f69fecf48d15e491a` |
| APK bytes | `103915440` |
| Android source base | `b079496816e617ffd891ea12e5bee5d116db1383` plus [complete source patch](../android/tensor/tensor-support.patch) |
| Comma JetLink base | v0.8.5, `4b747aebad3d8d96ab26d76f1668f2b2ecb1b667` plus [recovery patch](../patches/jetlink-usb-recovery/recovery.patch) |
| V2 source model SHA-256 | `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec` |

The installed APK was pulled back and matched byte for byte. Its signer matches the prior installation. The comma patch was checked against live source hashes, backed up, applied with fresh ignition-off telemetry, and verified after restarting its resident USB owner. The owner is running, USB is selected, V2 is selected, and the port is empty while the phone is at the desk. Stored engine readiness alone is not a fresh USB handshake. The comma had 53 GiB available and the Pixel reported 373.6 GB available.

Upstream `main` was checked through `a34ad5f3c38546d0915b112939f51a8cb4f57b18`. Its later adapter API change is not part of this repair. The comma's API-2 integration and submodule pin are retained; no unpublished submodule commit is required. The Jetson was not modified in this repair.

## Validation

| Check | Result |
| --- | --- |
| Android release build and unit tests | Build succeeded; 59 tests passed |
| Native USB, protocol and thermal suites | 41 tests across 7 suites passed |
| Comma transport, joining, model state and client tests | 217 tests and 9 subtests passed |
| New regressions on original code | Receive-reserve regression failed; all 5 new comma regression cases failed |
| Patch installer | Dry-run, apply/readback, idempotence and rejection of unexpected local changes passed |
| Source reconstruction | Complete Android patch applies to clean pinned upstream source; comma patch verifies exact before/after hashes |
| Numerical comparison | All 15 slices passed across 32 recurrent frames; all 64 input arrays match the original reference byte for byte |
| Installed app desk inference | 1,200/1,200 finite frames; no protocol or health failures |

The native USB session tests used the pinned ONNX Runtime 1.29.0 Linux runtime with its download hash verified. Tests exercise simulated transport and native CPU fixtures, not a physical comma-to-Pixel cable.

Desk timing is **ADB/TCP**, not direct comma USB:

| Metric | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Tensor inference | 34.576 ms | 36.268 ms | 39.933 ms |
| Phone total processing | 35.831 ms | 37.646 ms | 41.053 ms |
| Desk round trip | 51.612 ms | 59.161 ms | 77.284 ms |

Android reported normal thermal status throughout; battery readings ranged from 30.1 to 31.0°C. The desk round trip did not meet a 50 ms budget: 837 of 1,200 frames exceeded it. This run verifies the installed app's numerical behavior, protocol and phone processing, **not driving readiness**. [Machine-readable results](../android/tensor/usb-recovery-2026-10-10.json).

## Reapply and rollback on the comma

This repair is an explicit patch against the pinned JetLink source. It is not automatically applied by the older installation branch or a clean upstream checkout. Preserve the patch bundle and recheck after any JetLink update; never force it onto different sources.

With this repository available locally, check or apply to its `jetlink_repo` using:

```sh
python scripts/maintenance/apply_jetlink_usb_recovery.py --check
python scripts/maintenance/apply_jetlink_usb_recovery.py
```

For the installed comma, the deployment bundle is `/data/jetlink-usb-recovery-20261010`. With ignition off, run from `/data/openpilot`:

```sh
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python \
  /data/jetlink-usb-recovery-20261010/apply.py \
  --root /data/openpilot/jetlink_repo \
  --bundle /data/jetlink-usb-recovery-20261010 --check
```

Omit `--check` to apply when original source hashes match. The installer validates fresh offroad/ignition/process telemetry before modifying a live comma, creates a rollback ZIP, and refuses unexpected or partially patched files. Already-patched files are verified without rewriting. Restart the USB owner only while offroad, or reboot with ignition off, after a new application.

The original installed files are in `/data/jetlink-usb-recovery-20261010/rollback-1791662427432335147.zip`. To roll back, first confirm ignition off and all onroad processes stopped; restore only its four listed source files into the same JetLink checkout, verify their `before` hashes in [manifest.json](../patches/jetlink-usb-recovery/manifest.json), then restart offroad. Do not overwrite unrelated local changes. The prior [Pixel APK and instructions](../android/README-0.8.5-clarity-tensor.5.md) remain archived; Android may refuse a version-code downgrade. Do not uninstall to bypass it and lose app data.

## Next physical test

1. Physically unplug the Android Auto adapter from the car. Use the same known Pixel-to-comma USB data/power path so this comparison changes one external workload.
2. Keep the car parked. The car may be on for air conditioning; keep the Pixel cooled. Open JetLink, connect it to the comma and accept the USB permission prompt if shown.
3. Verify a fresh protocol-v3 handshake, V2 identity, SuperSpeed enumeration and live phone health. Begin with 120 frames, then extend to 1,200 if timing and transport stay clean. Review camera-derived output, fallback/rejoin and both devices' logs before a drive.
4. A repeated disconnect, late-frame/fallback burst or thermal refusal fails this check. Preserve the timestamps and logs, then isolate cable/hub/power if resets continue. A desk pass or a stored ready flag does not override a failed physical test.

The normal app remains enabled for ordinary USB operation; this stationary procedure is a validation step, not a restored parked-only software gate.

The Pixel has a bounded USB/JetLink log capture running for this check: at most four files near 1 MiB each, expiring after one hour. It records selected USB/JetLink tags, not general application logs. The [capture script](../scripts/maintenance/capture_pixel_usb.sh) can be pushed with ADB and run using `adb shell sh /data/local/tmp/clarity-capture-pixel-usb.sh`; repeated starts reuse the active capture. Retrieve `/sdcard/Download/ClarityPilot-usb-test` after the test. The comma's normal route and rotating owner logs remain available. Keep raw logs private.
