# Pixel host USB receive mitigation — October 10, 2026

JetLink `0.8.5-clarity-tensor.9` is installed on the Pixel. Its exact APK is in `android/`, with the full source patch against upstream `b0794968`, checksum and rebuild instructions. Tensor G6, LiteRT 2.3.0 and the matched precompiled Cinque Terre V2 model are unchanged. The installed APK readback matches the repository APK; the temporary TCP listener and ADB forward were disabled after validation.

The latest drive's remaining fault was an endpoint `81` EPROTO completion: status `-71`, zero of 16,384 bytes. The paired comma switched to its small model for approximately 0.427 seconds and recovered. Assistance was inactive at that point. This does not demonstrate an inference failure or an engagement interruption. The comma's disconnect/configure kernel messages followed the Pixel error; they do not establish which side caused it.

[Linux USB documentation](https://www.kernel.org/doc/html/latest/driver-api/usb/error-codes.html) describes EPROTO as a bus-level error and explains that controllers may not distinguish a missing response, protocol fault or disconnect. Cable/device/controller causes remain possible. The logs do not prove wireless charging, screen state, or autosuspend caused this error.

## Change and evidence

The host receive ring now submits 64 requests of 8 KiB instead of 32 requests of 16 KiB. This retains the full 512 KiB receive reserve while reducing each usbfs transfer allocation. Eight KiB divides the unchanged 16 KiB protocol padding, so framing and protocol v3 remain compatible with both endpoints. The comma's existing 8 KiB FunctionFS send/receive patches remain installed. This is a buffer-size mitigation, not a demonstrated cure for EPROTO. Errors still terminate the session; failed bytes are not replayed into an active stream.

- Release build and 59 Android unit tests passed.
- 53 native tests passed, including multi-slot framing, receive reserve, ordered completions, bus-error propagation and cancel/reopen behavior.
- All 15 output slices passed a fresh 32-frame recurrent comparison with identical reference inputs and unchanged criteria.
- 1,200 measured ADB/TCP frames were finite with no protocol or health failure. Phone processing p95 was 37.045 ms, maximum 38.967 ms; inference p95 was 35.864 ms.
- ADB/TCP round-trip p95 was 56.256 ms, maximum 124.011 ms. Its timing check failed. It does not exercise the direct USB receive ring, so it cannot qualify driving or prove the mitigation fixed the dropout.

[Machine-readable results](../android/tensor/usb-host-buffer-2026-10-10.json).

## Next physical check

Keep the car in Park, connect the Pixel directly to the comma with a known-good USB data cable, leave the wireless charger and Android Auto adapter off for the first comparison, and cool the phone with AC if needed. Capture a fresh USB handshake and sustained inference with paired endpoint logs before considering another drive. Physical qualification after this update remains pending. No frame deadlines, fallback rules, controls thresholds or phone thermal protections were relaxed.

Rollback requires the archived `.8` source patch and rebuilding with a higher version code and the same signing key. Do not uninstall the app or force an Android downgrade, because that can remove imported models and settings.
