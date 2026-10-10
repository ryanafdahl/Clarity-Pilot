#!/usr/bin/env python3
"""Offroad-only, incremental rlog mileage collector. Its ledger is PRIVATE."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from core import DistanceCounter, METHOD_VERSION, METERS_PER_MILE


def atomic_json(path, value):
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix('.tmp')
  with temporary.open('w') as stream:
    json.dump(value, stream, indent=2, sort_keys=True)
    stream.write('\n')
    stream.flush()
    os.fsync(stream.fileno())
  os.replace(temporary, path)


def require_offroad():
  if Path('/data/params/d/IsOffroad').read_bytes().strip() != b'1':
    raise RuntimeError('Mileage collection is deferred while the comma is onroad')


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--root', type=Path, default=Path('/data/media/0/realdata'))
  parser.add_argument('--state', type=Path, required=True)
  parser.add_argument('--openpilot', default='/data/openpilot')
  parser.add_argument('--summary', type=Path, required=True)
  parser.add_argument('--minimum-age', type=int, default=120)
  args = parser.parse_args()
  require_offroad()
  args.state.parent.mkdir(parents=True, exist_ok=True)
  with args.state.with_suffix('.lock').open('w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ledger = json.loads(args.state.read_text()) if args.state.exists() else {'method_version': METHOD_VERSION, 'segments': {}}
    if ledger['method_version'] != METHOD_VERSION:
      raise RuntimeError('Ledger method changed; migrate explicitly before collecting')
    sys.path.insert(0, args.openpilot)
    import zstandard
    from openpilot.cereal import log
    scanned = skipped = reused = 0
    for path in sorted(args.root.glob('*/rlog.zst')):
      require_offroad()
      if path.is_symlink() or path.parent.is_symlink() or any(path.parent.glob('*.lock')) or time.time() - path.stat().st_mtime < args.minimum_age:
        skipped += 1
        continue
      key = hashlib.sha256(path.parent.name.encode()).hexdigest()
      stat = path.stat()
      fingerprint = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
      previous = ledger['segments'].get(key)
      if previous and previous['fingerprint'] == fingerprint:
        reused += 1
        continue
      counter = DistanceCounter()
      first_ns = last_ns = None
      wall_time_ns = None
      # Decode only the required fields. The general LogReader caches and sorts
      # every event; CAN traffic is irrelevant to this integration and expensive.
      with path.open('rb') as compressed, zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
        data = stream.read()
      samples = []
      for event in log.Event.read_multiple_bytes(data):
          kind = event.which()
          if kind == 'initData' and wall_time_ns is None:
            wall_time_ns = event.initData.wallTimeNanos
          if kind not in ('carState', 'carControl'):
            continue
          first_ns = event.logMonoTime if first_ns is None else min(first_ns, event.logMonoTime)
          last_ns = event.logMonoTime
          if kind == 'carControl':
            control = event.carControl
            samples.append((event.logMonoTime, 0, control.latActive, control.longActive, event.valid))
          else:
            car = event.carState
            samples.append((event.logMonoTime, 1, car.vEgo, event.valid and car.canValid, car.standstill))
      for timestamp_ns, kind, x, y, z in sorted(samples, key=lambda sample: sample[0]):
        if kind == 0:
          counter.control(timestamp_ns / 1e9, x, y, z)
        else:
          counter.speed(timestamp_ns / 1e9, x, y, z)
      require_offroad()
      after = path.stat()
      if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        raise RuntimeError('A log changed during collection; retry when it is closed')
      if not counter.speed_samples:
        skipped += 1
        continue
      ledger['segments'][key] = dict(counter.result(), fingerprint=fingerprint,
                                     route_key=hashlib.sha256(path.parent.name.rsplit('--', 1)[0].encode()).hexdigest(),
                                     first_monotonic_ns=first_ns, last_monotonic_ns=last_ns,
                                     wall_time_ns=wall_time_ns)
      atomic_json(args.state, ledger)
      scanned += 1
      if scanned % 10 == 0:
        print(json.dumps({'new_segments_processed': scanned}), flush=True)
    records = list(ledger['segments'].values())
    summary = {
      'method_version': METHOD_VERSION,
      'assisted_miles': sum(s['assisted_meters'] for s in records) / METERS_PER_MILE,
      'total_recorded_miles': sum(s['total_meters'] for s in records) / METERS_PER_MILE,
      'segments': len(records),
      'recordings': len({s['route_key'] for s in records}),
      'assisted_recordings': len({s['route_key'] for s in records if s['assisted_meters'] > 0}),
      'observed_hours': sum(s['observed_seconds'] for s in records) / 3600,
      'assisted_hours': sum(s['assisted_seconds'] for s in records) / 3600,
      'skipped_intervals': sum(s['skipped_intervals'] for s in records),
      'scanned_this_run': scanned,
      'reused_this_run': reused,
      'deferred_this_run': skipped,
      'collected_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    atomic_json(args.summary, summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
  main()
