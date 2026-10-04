# JetLink update — October 4, 2026

Both devices were updated for the current JetLink integration. The comma rebooted successfully; the Jetson service is running with Cinque Terre V2 loaded. The devices were disconnected during verification. A direct USB handshake and ignition-on parked test remain pending.

## Installed versions

| Component | Verified revision |
| --- | --- |
| Jetson server | [v0.8.3](https://github.com/zoompilot/jetlink/releases/tag/v0.8.3), release commit `f49d740`, published October 4 at 19:11:33 UTC |
| Comma JetLink client | `fd42477e13d0eb093594be8e7074e9ca2d544dff`, protocol v3; the commit after v0.8.3 adds the shadow-frame timing gate |
| Integration reference | [zoompilot develop `b56bbccc`](https://github.com/zoompilot/zoompilot/commit/b56bbccc415061cd599d5f1ea8b97083dff59f6b) |
| Installed comma deployment | [ryanafdahl/openpilot, Clarity-Pilot, `f35471af`](https://github.com/ryanafdahl/openpilot/commit/f35471af9756181166393e9da61ddf8bf3d4a5d0) |
| sunnypilot base | `a5f44653d7f43ad57fef2f546f3916ec4cbf3c56`, already incorporated; still the current master at the final upstream check |
| Small model | CD210 Model (February 03, 2026), preserved |
| Large model | Cinque Terre Model V2 (September 08, 2026), preserved on comma and Jetson |
| Jetson platform | Ubuntu 24.04.4, L4T 39.2.1, TensorRT 10.16.2.10, Orin Nano Super 8 GB |
| Pixel | Unchanged: `0.8.0-clarity-tensor.4`, version code 804; experimental Tensor mode remains parked-only |

The server release archive SHA-256 is `e43a9403a59b06dc434a0adda08dc56475627cc964ab66f0eb57024873287643`. V2's source model SHA-256 is `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec` (766,040,736 bytes). The existing Jetson TensorRT engine was retained and successfully reloaded.

The [upstream changelog](https://zoompilot.ai/jetlink/#log) was checked together with GitHub releases and branch tips. v0.8.3 was the latest published release at the final check. General Ubuntu security packages and NVIDIA platform upgrades were outside this JetLink update; this report does not assert that every OS package is current.

## What changed

- Replaced the fork's older private accelerator package with the current `jetlink.openpilot` adapter and resident USB owner. The owner keeps the gadget across ignition transitions and lends endpoints to provisioning/modeld.
- Imported the matching upstream model warmup, shadow inference and timing proof before switching to the large model, prior-output handling for a late frame, repeated-lateness handback, reconnect behavior and status UI.
- Integrated the nonblocking shutdown request, one-second transition settling and matching MADS paused-state handling. Other Clarity vehicle behavior and custom event IDs were preserved.
- Migrated the installed link setting to `JetlinkLink=1` (USB), populated V2's model pointer, and disabled ADB while JetLink owns the port. Old settings remain available for rollback. Engine readiness was established through a real server handshake, not fabricated from the enabled setting.
- Retained first-install TCPMV3 provisioning and included it in the deployment branch. Existing CD210 selection was preserved. The upstream empty-slot large-model default is V3; **this installation explicitly selects V2**.
- Preserved the private Pixel parked-only peer rejection. The legacy bench, replay and Pixel test harness now refuse the new adapter before starting. Both staged Pixel harness copies on the comma were guarded; the old ignition-on manifest was not changed to bypass its review requirement.

The Jetson update preserved the engine cache, web sign-in, switched-power configuration and retired USB-Wi-Fi setup. A temporary, bounded TCP validation service was stopped after the smoke check and the normal USB service restored. No persistent TCP-serving configuration was added.

## Validation

| Check | Result |
| --- | --- |
| Full installed comma SCons build | Passed, including the 1344×760 → 512×256 tinygrad image warp |
| Installed integration suite | 384 tests: **378 passed, 6 skipped** |
| Upstream protocol, client, USB owner/lending, adapter and watchdog suite | **851 passed, 1 skipped**, plus 56 passing subtests |
| Selfdrived transition traces | **8 passed** |
| Legacy tool refusal checks | Bench, replay and Pixel ignition-on harness each exited before testing or modifying settings |
| Updated comma → Jetson protocol check | Protocol v3; V2 cache accepted; **21 finite synthetic frames**, including full raw output |
| Comma reboot | UI, pandad, hardwared, models_manager and jetlinkd running; fresh offroad/no-ignition state; no camera/modeld process expected while offroad |
| Post-reboot selection | CD210 and V2 unchanged; Jetlink USB enabled; ADB off; owner reports no error and no attached cable |
| Jetson after validation | Native 0.8.3 service active, V2 engine ready, zero automatic restarts |
| Storage | Comma: about 57 GiB available; Jetson: about 1.7 TiB available; existing retention policy preserved |

The six integration skips cover three comparisons requiring a local upstream develop branch, an obsolete upstream warp helper, an optional legacy-model fixture and a live-network manifest test. GUI rendering and real camera/vehicle operation were not exercised by this suite. The upstream consolidated run initially exposed two tests assuming the monotonic clock is beyond the five-second presence hold on a freshly started WSL instance; the unchanged suite passed after that interval. An earlier isolated subprocess dependency issue was also fixed in the test environment before the final run.

The synthetic exchange used **desk TCP, not USB**. Mean round trip was **84.92 ms**, maximum **103.34 ms**. These figures do **not** meet or establish the 50 ms driving budget. The purpose was to check protocol/model compatibility and finite/raw output with the installed versions. No synthetic outputs were published into vehicle controls. [Sanitized smoke-check evidence](validation/jetlink-083-smoke.json).

The post-reboot readiness record says that V2 was prepared; `present=false` correctly reports the disconnected cable. It is not evidence of a live USB session. September/October 3 drive reports and Pixel timing results describe older software and remain historical evidence.

## Next parked check

1. Leave the car powered off. Power the Jetson and comma, then connect **Jetson USB-A → comma USB-C** using the intended USB 3 data cable.
2. Confirm the resident owner sees the host, negotiates the link and completes a new protocol-v3 handshake with the Jetson. Confirm Cinque Terre V2 and its engine hash on both sides.
3. After that connection check, perform a supervised ignition-on stationary test: verify small-model startup, shadow preparation, large-model activation, timing and clean handback/reconnection with controls disengaged. Collect bounded evidence from both devices.

A new driving test is not qualified by this software update, reboot or desk smoke check. Pixel test isolation/borrowing must be reviewed against the new adapter before another Pixel session can be armed; the prior manifest and timing failures remain in place.

## Recovery records

The comma retains local branch `backup/jetlink-pre-083-20261004`, the pre-update selected settings and changed-file archive under `/data/jetlink-083-update/`. The Jetson retains `/var/backups/jetlink-pre-083-20261004.tar.gz` and `/opt/jetlink/previous` points to 0.8.0. Settings backups stay on the devices because they can include private configuration. Roll back code, settings and runtime together while offroad if necessary; do not restore a readiness flag as a substitute for a new handshake.

The source-of-record repository and the separately installed deployment repository have different histories. Both are published explicitly; pushing Clarity-Pilot/main alone does not install it on the comma.
