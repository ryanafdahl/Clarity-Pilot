"""Validate per-frame correlation metadata without a phone or model."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np


class Client:
    last_timings = (34000, 300, 35000)
    last_state = {}
    @staticmethod
    def open_tcp(*args, **kwargs): return Client()
    def hello(self): return {'backend':'fixture', 'device':'fixture'}
    def ensure_engine(self, *args): return None
    def infer(self, *args, frame_id, **kwargs): return np.array([frame_id],dtype=np.float32)
    def close(self): pass


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        fake = {'jetlink.client': types.SimpleNamespace(JetlinkClient=Client),
                'scripts.verify_parity': types.SimpleNamespace(make_inputs=lambda *a, **k: [(None, None)]*32)}
        spec = importlib.util.spec_from_file_location('testable_benchmark',Path(__file__).with_name('benchmark.py'))
        self.benchmark = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, fake): spec.loader.exec_module(self.benchmark)

    def test_per_frame_ids_warmup_and_output_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, frames = Path(tmp)/'run.json', Path(tmp)/'frames.json'
            argv=['benchmark','--source-sha256','fixture','--source-bytes','1','--frames','10',
                  '--warmup','2','--period-ms','0','--transport','fixture',
                  '--output',str(result),'--frame-output',str(frames)]
            with patch.object(sys,'argv',argv), patch.object(self.benchmark,'first_health',return_value={}), \
                 patch.object(self.benchmark,'device_health',return_value={}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.benchmark.main(),0)
            data=json.loads(frames.read_text())['frames']
            self.assertEqual([f['frame_id'] for f in data],list(range(12)))
            self.assertEqual([f['frame_id'] for f in data if f['warmup']],[0,1])
            self.assertEqual(len({f['output_sha256'] for f in data}),12)
            self.assertTrue(all(f['server_total_ms']==35 for f in data))
            self.assertEqual(json.loads(result.read_text())['measured_frames'],10)

    def test_refuses_output_collision_before_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=str(Path(tmp)/'same.json')
            argv=['benchmark','--source-sha256','fixture','--source-bytes','1',
                  '--transport','fixture','--output',target,'--frame-output',target]
            with patch.object(sys,'argv',argv), patch.object(Client,'open_tcp') as connect, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.benchmark.main()
            connect.assert_not_called()


if __name__=='__main__': unittest.main()
