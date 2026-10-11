import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collect_model_usage import main


class ModelCollectionTests(unittest.TestCase):
  def write_log(self, path, compact, peer=None):
    import zstandard
    from openpilot.cereal import log
    events = []
    def event(kind, t):
      e = log.Event.new_message()
      e.logMonoTime = int(t*1e9)
      e.valid = True
      if kind == 'logMessage': e.logMessage = ''
      else: e.init(kind)
      events.append(e)
      return getattr(e, kind)
    event('initData', 0).wallTimeNanos = 1791000000000000000
    if peer: event('logMessage', 0)  # primitive Text is set on its parent below
    if peer: events[-1].logMessage = f'jetlink: {peer} trt None, engine none, loaded abc'
    for i in range(11):
      t = i/10
      event('carControl', t).latActive = True
      car = event('carState', t); car.vEgo = 10; car.canValid = True
      if not compact or i%5 == 0:
        event('drivingModelData' if compact else 'modelV2', t).big = True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zstandard.ZstdCompressor().compress(b''.join(e.to_bytes() for e in events)))
    os.utime(path, (1000000000, 1000000000))

  def run_collector(self, root, base):
    with patch('collect_model_usage.require_offroad'), patch('sys.argv', ['collect_model_usage.py', '--root', str(root), '--base', str(base)]), contextlib.redirect_stdout(io.StringIO()):
      main()
    return json.loads((base/'model-usage-ledger.json').read_text())['segments']

  def test_real_compact_log_recovers_big_model_without_invented_peer(self):
    with tempfile.TemporaryDirectory() as d:
      root, base = Path(d)/'logs', Path(d)/'state'
      self.write_log(root/'route--0/qlog.zst', True)
      rows = list(self.run_collector(root, base).values())
      self.assertEqual(rows[0]['source_kind'], 'qlog')
      self.assertAlmostEqual(rows[0]['buckets']['large_unknown']['assisted_meters'], 10)
      self.assertEqual(rows[0]['buckets']['jetson']['assisted_meters'], 0)

  def test_full_rate_replaces_compact_once_and_survives_original_cleanup(self):
    with tempfile.TemporaryDirectory() as d:
      root, base = Path(d)/'logs', Path(d)/'state'
      folder = root/'route--0'
      self.write_log(folder/'qlog.zst', True)
      self.run_collector(root, base)
      self.write_log(folder/'rlog.zst', False, 'tensor-Tensor_G6')
      rows = list(self.run_collector(root, base).values())
      self.assertEqual(len(rows), 1)
      self.assertEqual(rows[0]['source_kind'], 'rlog')
      self.assertAlmostEqual(rows[0]['buckets']['pixel']['assisted_meters'], 10)
      (folder/'rlog.zst').unlink()
      again = list(self.run_collector(root, base).values())
      self.assertEqual(again, rows)
