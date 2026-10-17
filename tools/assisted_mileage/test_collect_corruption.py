"""Regression: a truncated recording cannot block other mileage or erase prior evidence."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import zstandard
from openpilot.cereal import log
import collect
import collect_model_usage
from core import METHOD_VERSION


def recording():
  events = []
  for ns in (1_000_000_000, 1_050_000_000, 1_100_000_000):
    events.append(log.Event.new_message(logMonoTime=ns, valid=True,
                  carControl={'latActive': True, 'longActive': False}).to_bytes())
    events.append(log.Event.new_message(logMonoTime=ns, valid=True,
                  carState={'vEgo': 10.0, 'canValid': True, 'standstill': False}).to_bytes())
  return b''.join(events)


class CorruptRecordings(unittest.TestCase):
  def test_unreadable_segments_do_not_block_or_replace_verified_records(self):
    with tempfile.TemporaryDirectory() as tmp:
      base = Path(tmp); root = base/'logs'; state = base/'ledger.json'; summary = base/'summary.json'
      payload = recording()
      for segment, raw in ((0, payload), (1, payload[:-3]), (3, payload)):
        p = root/f'test-route--{segment}'/'rlog.zst'; p.parent.mkdir(parents=True)
        p.write_bytes(zstandard.ZstdCompressor().compress(raw))
      p = root/'test-route--2'/'rlog.zst'; p.parent.mkdir(parents=True);p.write_bytes(b'not zstd')
      args = ['collect.py', '--root', str(root), '--state', str(state), '--summary', str(summary), '--minimum-age', '0']
      with patch.object(sys, 'argv', args), patch.object(collect, 'require_offroad'), contextlib.redirect_stdout(io.StringIO()):
        collect.main()
        first = json.loads(summary.read_text());ledger = json.loads(state.read_text())
        self.assertEqual(first['scanned_this_run'], 2)
        self.assertEqual(first['unreadable_this_run'], 2)
        self.assertEqual(len(ledger['segments']), 2)
        self.assertGreater(first['assisted_miles'], 0)
        # Seed a prior successful observation for the now-truncated segment.
        badkey = hashlib.sha256(b'test-route--1').hexdigest()
        prior = dict(next(iter(ledger['segments'].values())))
        prior['fingerprint'] = {'size': -1, 'mtime_ns': -1}
        ledger['segments'][badkey] = prior
        collect.atomic_json(state, ledger)
        collect.main()
        second = json.loads(summary.read_text())
        self.assertEqual(second['scanned_this_run'], 0)
        self.assertEqual(second['reused_this_run'], 2)
        self.assertEqual(second['unreadable_this_run'], 2)
        self.assertEqual(json.loads(state.read_text())['segments'][badkey], prior)
        self.assertEqual(second['segments'], 3)

  def test_model_collector_preserves_history_and_does_not_cache_bad_files(self):
    with tempfile.TemporaryDirectory() as tmp:
      base = Path(tmp); root = base/'logs'; payload = recording()
      for segment, raw in ((0, payload), (1, payload[:-3]), (3, payload)):
        p = root/f'test-route--{segment}'/'rlog.zst'; p.parent.mkdir(parents=True)
        p.write_bytes(zstandard.ZstdCompressor().compress(raw)); os.utime(p, (1, 1))
      p = root/'test-route--2'/'rlog.zst';p.parent.mkdir(parents=True);p.write_bytes(b'not zstd');os.utime(p, (1, 1))
      args = ['collect_model_usage.py', '--root', str(root), '--base', str(base)]
      with patch.object(sys, 'argv', args), patch.object(collect_model_usage, 'require_offroad'), contextlib.redirect_stdout(io.StringIO()):
        collect_model_usage.main()
        summary = json.loads((base/'model-usage-summary.json').read_text())
        ledger = json.loads((base/'model-usage-ledger.json').read_text())
        self.assertEqual(summary['scanned_this_run'], 2)
        self.assertEqual(summary['unreadable_this_run'], 2)
        self.assertEqual(len(ledger['segments']), 2)
        badkey = hashlib.sha256(b'test-route--1').hexdigest()
        prior = dict(next(iter(ledger['segments'].values())))
        prior['fingerprint'] = {'size': -1, 'mtime_ns': -1}
        ledger['segments'][badkey] = prior
        collect.atomic_json(base/'model-usage-ledger.json', ledger)
        collect_model_usage.main()
        summary = json.loads((base/'model-usage-summary.json').read_text())
        self.assertEqual(summary['scanned_this_run'], 0)
        self.assertEqual(summary['reused_this_run'], 2)
        self.assertEqual(summary['unreadable_this_run'], 2)
        self.assertEqual(json.loads((base/'model-usage-ledger.json').read_text())['segments'][badkey], prior)


if __name__ == '__main__':
  unittest.main()
