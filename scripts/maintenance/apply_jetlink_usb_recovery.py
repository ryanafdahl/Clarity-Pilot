#!/usr/bin/env python3
"""Apply the reviewed USB recovery patch only to its exact source files.

Run with the comma offroad using its openpilot Python environment. Re-running
is harmless. No parameters, control thresholds, or submodule pins are changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile


def apply(root, bundle, check_only=False):
  root=root.resolve(); bundle=bundle.resolve()
  manifest=json.loads((bundle/'manifest.json').read_text())
  states=[]
  for name, hashes in manifest['files'].items():
    path=(root/name).resolve()
    if not path.is_relative_to(root): raise RuntimeError('Patch path escapes checkout')
    digest=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    if digest not in hashes.values(): raise RuntimeError(f'Unexpected local version: {name}; nothing changed')
    states.append('after' if digest==hashes['after'] else 'before')
  if all(s=='after' for s in states):
    print('USB recovery patch already installed and verified');return
  if any(s=='after' for s in states): raise RuntimeError('Partially applied patch; restore or inspect before retrying')
  patch=bundle/'recovery.patch'
  subprocess.run(['git','-C',str(root),'apply','--check',str(patch)],check=True)
  if check_only:
    print('Exact original sources verified; patch applies');return
  # A live comma must have fresh offroad/ignition evidence, not only a saved param.
  if root==Path('/data/openpilot/jetlink_repo').resolve():
    sys.path.insert(0,'/data/openpilot')
    from openpilot.common.params import Params
    from openpilot.cereal import messaging
    sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
    for _ in range(20):
      sm.update(250)
      if all(sm.seen.values()) and all(sm.alive.values()):break
    if not all(sm.seen.values()) or not all(sm.alive.values()) or not all(sm.valid.values()):
      raise RuntimeError('Fresh device/ignition/process telemetry unavailable')
    if not Params().get_bool('IsOffroad') or sm['deviceState'].started or not len(sm['pandaStates']) or any(x.ignitionLine or x.ignitionCan for x in sm['pandaStates']):
      raise RuntimeError('Apply only with car ignition off and comma offroad')
    if any(x.running and x.name in ('camerad','modeld','modeld_tinygrad','controlsd','selfdrived') for x in sm['managerState'].processes):
      raise RuntimeError('Onroad processes are still running')
  backup=bundle/f'rollback-{time.time_ns()}.zip'
  with zipfile.ZipFile(backup,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for name in manifest['files']:z.write(root/name,name)
  subprocess.run(['git','-C',str(root),'apply',str(patch)],check=True)
  for name,hashes in manifest['files'].items():
    if hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=hashes['after']:
      raise RuntimeError(f'Post-apply verification failed: {name}; backup {backup}')
  print(f'Installed and verified; rollback sources: {backup}')


if __name__=='__main__':
  parser=argparse.ArgumentParser(description=__doc__)
  repo=Path(__file__).resolve().parents[2]
  parser.add_argument('--root',type=Path,default=repo/'jetlink_repo')
  parser.add_argument('--bundle',type=Path,default=repo/'patches/jetlink-usb-recovery')
  parser.add_argument('--check',action='store_true')
  args=parser.parse_args()
  apply(args.root,args.bundle,args.check)
