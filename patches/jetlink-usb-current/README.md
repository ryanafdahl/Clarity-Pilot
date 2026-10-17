# Exact comma USB recovery bundle

This consolidates the three October 10 USB recovery/stability/receive patches
already installed on the maintained comma. It changes no protocol, model,
control threshold, or timing deadline. All eight final file hashes were checked
against the live device on October 17, 2026.

Base JetLink revision: `4b747aebad3d8d96ab26d76f1668f2b2ecb1b667` (v0.8.5).
The native Jetson server can be v0.8.7; the comma adapter remains API 2.

After a fresh comma installation, with ignition off and the normal offroad UI
running, apply the bundle once from the installation checkout:

```sh
cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python scripts/maintenance/apply_jetlink_usb_recovery.py --bundle patches/jetlink-usb-current
sudo reboot
```

The installer verifies exact original or fully patched files before doing
anything, refuses unknown/partially patched sources, and makes a rollback ZIP
before a live change. A device already on the final patch prints
`USB recovery patch already installed and verified`. Do not apply the older
three bundles afterward. This bundle is included in the source and reinstall
repositories; application on a fresh install remains an explicit offroad step.

Preserve settings, selected models, and the separate private mileage ledger
before reinstalling. Confirm a parked USB connection after reboot; the October
17 desk TCP check does not qualify USB or vehicle behavior.
