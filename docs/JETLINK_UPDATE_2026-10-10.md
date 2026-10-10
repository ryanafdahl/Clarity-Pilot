# JetLink update and Clarity Pilot branding — October 10, 2026

The comma and Jetson now use JetLink **0.8.5**. The comma home screen displays **Clarity Pilot**; the comma 4 label uses a smaller font so the full name fits its 480-pixel area. The matching runtime changes are published in both the source repository and the installation branch.

## Reinstallation

Enter **`installer.comma.ai/ryanafdahl/Clarity-Pilot`** in the comma Custom Software installer. This resolves to **`ryanafdahl/openpilot`, branch `Clarity-Pilot`**, rather than this source repository's `main` branch.

- Source: [ryanafdahl/Clarity-Pilot, main](https://github.com/ryanafdahl/Clarity-Pilot/tree/main).
- Installation branch: [ryanafdahl/openpilot, Clarity-Pilot](https://github.com/ryanafdahl/openpilot/tree/Clarity-Pilot).
- JetLink integration commit: [`95e5834f`](https://github.com/ryanafdahl/openpilot/commit/95e5834f59d1b3766e46700d14b9117b857a9455).
- Home-screen branding commit: [`9369cf07`](https://github.com/ryanafdahl/openpilot/commit/9369cf07a5afa216283f07519af2c4adb483bf46).

Both runtime commits are included in the installation branch. Preserve settings and needed logs before reinstalling. After normal setup and calibration, keep the comma online while parked, select CD210 and Cinque Terre V2 as appropriate, and confirm the USB connection and engine identity before vehicle testing. Device settings and cached models are not a substitute for the published code and may need to be restored after a fresh install.

## Version pins and changes

| Component | Revision |
| --- | --- |
| JetLink client and native Jetson server | [v0.8.5](https://github.com/zoompilot/jetlink/releases/tag/v0.8.5), commit `4b747aebad3d8d96ab26d76f1668f2b2ecb1b667` |
| Matching upstream integration | [zoompilot `2118dd7c`](https://github.com/zoompilot/zoompilot/commit/2118dd7c3ac7adaa98874b22c89d5a5a34a3744c) |
| Protocol / adapter | Protocol 3 / adapter API 2 |
| Small model | CD210, ref `5b6436a90cf6902b8aaa71c2b6f3d7164d8ae391` |
| Large model | Cinque Terre V2, ref `37bfa1413edcdc2e8844984b83727c33f81d8f46` |
| V2 model SHA-256 | `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec` |
| Jetson runtime | L4T 39.2.1, TensorRT 10.16.2.10, MAXN_SUPER |

The port updates engagement-aware adapter inputs, both modeld integrations, bounded model-startup guards, the matching MADS first-load gate, and model download/readiness status. The phone-charging parameter defaults off. Existing parked-only Pixel protection, model selections, EPS firmware and steering settings are preserved.

The Jetson received 246 Ubuntu security-package upgrades with no additions or removals. Kernel, NVIDIA, CUDA and TensorRT packages were excluded. After reboot its cached V2 engine was ready at +11.9 seconds; JetLink reported zero service restarts, package audit was clean, and no installed package had a newer candidate from the checked Ubuntu security origin. General updates and Ubuntu Pro/ESM packages were outside scope.

## Validation and limits

- Full installed comma SCons build passed, including the hardware warp build.
- Installed integration: 387 tests run, 381 passed and six skipped.
- Installed model-startup/MADS checks: 16 passed.
- JetLink Linux regressions: 955 passed, two skipped, and 64 subtests passed.
- Updated endpoints exchanged 21 finite synthetic frames, including full raw output, with protocol 3 and the expected V2 engine identity.

That synthetic exchange used desk TCP during other checks: mean 86.87 ms, maximum 113.45 ms. It verifies compatibility, not a 50 ms budget or USB driving performance. The temporary server was stopped and normal USB service restored. Post-update reboot checks preserved offroad/no-ignition state, the selected models, USB mode and disabled ADB; expected offroad services ran.

The latest retained drive was on the **previous 0.8.3 build**: 54 full-rate log segments contained 64,175 consecutive large-model outputs, 26.44 ms mean reported execution, 29.04 ms p95 and 46.18 ms maximum. Earlier sessions included handbacks and a brief soft-disabling interval. See the [sanitized maintenance analysis](https://t3st.site/maintenance-005.html). Raw logs, route identifiers and location data remain private.

New cold-start USB and supervised vehicle validation remain pending. Three pre-existing Jetson networking units also remain failed: dnsmasq cannot bind port 53, while the IPv4/IPv6 ISC DHCP units have no configured listening interfaces/subnets. Existing Ethernet access and JetLink service operation were verified; unrelated network configuration was not changed.

## Rollback

The comma retains branch `backup/jetlink-pre-085-20261010`, plus private parameter and tracked-file backups under `/data/maintenance/20261010`. The Jetson retains its previous release directory and a private configuration backup at `/var/backups/jetlink-pre-085-20261010.tar.gz`. Rollback is an offroad maintenance operation and must keep the client and server compatible.
