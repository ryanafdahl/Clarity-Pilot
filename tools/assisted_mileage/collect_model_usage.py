"""Offroad-only incremental model attribution; durable private segment ledger."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time

from collect import atomic_json, require_offroad
from model_usage import ModelUsageCounter, VERSION, ATTRIBUTION_REVISION, carried_peer, peer_from_message, summarize


def segment_order(path):
  route, segment = path.parent.name.rsplit('--', 1)
  return route, int(segment)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--root', type=Path, default=Path('/data/media/0/realdata'))
  parser.add_argument('--base', type=Path, default=Path(__file__).resolve().parent)
  parser.add_argument('--budget-seconds', type=float, default=180)
  args = parser.parse_args()
  require_offroad()
  args.base.mkdir(parents=True, exist_ok=True)
  with (args.base/'model-usage.lock').open('w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = args.base/'model-usage-ledger.json'
    ledger = json.loads(path.read_text()) if path.exists() else {'version': VERSION, 'segments': {}}
    if ledger['version'] != VERSION:
      raise RuntimeError('Model usage ledger version changed; migrate explicitly')
    sys.path.insert(0, '/data/openpilot')
    import zstandard
    from openpilot.cereal import log
    deadline = time.monotonic() + args.budget_seconds
    scanned = reused = 0
    last_route = last_index = last_record = None
    for source in sorted(args.root.glob('*/rlog.zst'), key=segment_order):
      require_offroad()
      if time.monotonic() >= deadline:
        break
      if source.is_symlink() or source.parent.is_symlink() or any(source.parent.glob('*.lock')):
        continue
      stat = source.stat()
      if time.time() - stat.st_mtime < 120:
        continue
      route, index = segment_order(source)
      key = hashlib.sha256(source.parent.name.encode()).hexdigest()
      fingerprint = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
      cached = ledger['segments'].get(key)
      if cached and cached['fingerprint'] == fingerprint and cached.get('attribution_revision') == ATTRIBUTION_REVISION:
        last_route, last_index, last_record = route, index, cached
        reused += 1
        continue
      with source.open('rb') as compressed, zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
        raw = stream.read()
      samples = []
      wall_time_ns = None
      for event in log.Event.read_multiple_bytes(raw):
        kind, t = event.which(), event.logMonoTime / 1e9
        if kind == 'initData' and wall_time_ns is None:
          wall_time_ns = event.initData.wallTimeNanos
        if kind == 'carState':
          car = event.carState
          samples.append((t, 3, car.vEgo, event.valid and car.canValid, car.standstill))
        elif kind == 'carControl':
          control = event.carControl
          samples.append((t, 1, bool(control.latActive or control.longActive), event.valid))
        elif kind == 'modelV2':
          samples.append((t, 2, bool(event.modelV2.big), event.valid))
        elif kind in ('logMessage', 'errorLogMessage'):
          raw_message = str(getattr(event, kind))
          try:
            obj = json.loads(raw_message)
            message = obj.get('msg', obj.get('msg$s', '')) if isinstance(obj, dict) else raw_message
          except ValueError:
            message = raw_message
          peer = peer_from_message(message)
          if peer is not None:
            samples.append((t, 0, peer, True))
      samples.sort(key=lambda row: (row[0], row[1]))
      if not samples:
        continue
      peer, peer_since = carried_peer(last_record, last_route == route and last_index == index - 1, samples[0][0])
      counter = ModelUsageCounter(peer, peer_since)
      for row in samples:
        t, kind = row[:2]
        if kind == 3:
          counter.speed(t, *row[2:])
        else:
          counter.event(t, ('peer', 'control', 'model')[kind], *row[2:])
      require_offroad()
      after = source.stat()
      if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('Log changed while being analyzed')
      record = dict(counter.result(), fingerprint=fingerprint, attribution_revision=ATTRIBUTION_REVISION,
                    wall_time_ns=wall_time_ns,
                    first_monotonic=samples[0][0], last_monotonic=samples[-1][0],
                    route_key=hashlib.sha256(route.encode()).hexdigest())
      ledger['segments'][key] = record
      atomic_json(path, ledger)
      last_route, last_index, last_record = route, index, record
      scanned += 1
    summary = summarize(list(ledger['segments'].values()))
    summary['scanned_this_run'] = scanned
    summary['reused_this_run'] = reused
    atomic_json(args.base/'model-usage-summary.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
  main()
