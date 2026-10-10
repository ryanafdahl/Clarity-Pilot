# Pixel USB receive mitigation — October 10, 2026

The latest drive's second and third fallbacks followed five consecutive held frames. The kernel USB disconnect occurred after the fallback, consistent with recovery resetting the gadget. Those resets do not by themselves establish a physical cable failure. The last successful server timing does not measure the unanswered invocation.

The comma still requested a contiguous 16 KiB kernel buffer for each incoming FunctionFS read. Existing transport notes identify higher-order allocation stalls under memory pressure. The receive path now uses 8 KiB chunks, matching the allocation-size bound already used for writes. A typical 8,356-byte reply spans two reads. The userspace pool remains 128 KiB. The earlier transport benchmark documented approximately 0.3 ms additional median cost for this split; fresh direct-USB timing remains pending.

This removes a known allocation risk. It does **not** prove memory allocation caused the three drive interruptions, eliminate all possible stalls, or establish ride readiness. The Pixel remains on the previously verified `.8` APK with matched LiteRT 2.3 and precompiled Cinque Terre V2; no Android code or model change was required for this comma-side mitigation.

## Verification and installation

- The new bounded-read regression failed in all three response sizes against the previous source.
- After the change, 193 transport, client, model-state and joining tests plus seven subtests passed.
- Responses of 8,356 bytes, full model outputs and 2 MiB reassembled correctly; queue limits and packet alignment remained covered.
- Installer dry-run, application, hash readback, idempotence and refusal of unknown source passed.
- Installed on the comma with fresh ignition-off/offroad/process checks and restarted its resident USB owner. The disconnected Pixel is an expected desk state, not a handshake pass.
- Existing deadlines, one-request USB backpressure, held-frame fallback, thermal refusal and model-swap protections remain unchanged.

Apply after the recovery and stability bundles:

```sh
python scripts/maintenance/apply_jetlink_usb_recovery.py --bundle patches/jetlink-usb-receive --check
python scripts/maintenance/apply_jetlink_usb_recovery.py --bundle patches/jetlink-usb-receive
```

The live bundle is `/data/jetlink-usb-receive-20261010`; rollback sources are in `rollback-1791671705485694960.zip` there. Restore only its two manifest-listed files after verifying ignition off, then check their before hashes and restart the owner offroad. Repository publication does not deploy to other devices.

## Next check

Connect the cool Pixel directly with the USB data cable, initially with the car off. Confirm fresh protocol v3, V2 identity, USB speed and current phone health. Then test with the car in Park; AC may run for cooling. Begin with 120 frames and extend to 1,200 only if clean. Capture both endpoints through any interruption. Keep the screen off, Android Auto disconnected and wireless charging off for this controlled comparison. Any fallback or reset remains a failed stability check requiring analysis before a ride.
