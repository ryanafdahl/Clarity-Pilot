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

    def test_wake_requires_explicit_device_before_connecting(self):
        argv=['benchmark','--source-sha256','fixture','--source-bytes','1',
              '--transport','fixture','--output','absent.json','--wake-frame','20']
        with patch.object(sys,'argv',argv),patch.object(Client,'open_tcp') as connect, \
             contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.benchmark.main()
        connect.assert_not_called()

    def test_single_wake_is_recorded_and_failure_is_not_a_pass(self):
        for fail in (False,True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as tmp:
                result=Path(tmp)/'run.json'
                calls=[]
                def run(command,**kwargs):
                    calls.append(command)
                    if command[-3:]==['input','keyevent','224'] and fail:
                        raise RuntimeError('fixture wake failure')
                    return types.SimpleNamespace(stdout='Thermal Status: 0\ntemperature: 290')
                argv=['benchmark','--source-sha256','fixture','--source-bytes','1','--frames','10',
                      '--warmup','2','--period-ms','0','--transport','fixture','--adb','fixture-adb',
                      '--serial','fixture-device','--wake-frame','2','--output',str(result)]
                with patch.object(sys,'argv',argv),patch.object(self.benchmark.subprocess,'run',side_effect=run), \
                     patch.object(self.benchmark,'first_health',return_value={}), \
                     patch.object(self.benchmark,'device_health',return_value={}),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(self.benchmark.main(),1 if fail else 0)
                data=json.loads(result.read_text())
                self.assertEqual(sum(c[-3:]==['input','keyevent','224'] for c in calls),1)
                self.assertEqual(data['wake_stimulus']['frame_id'],2)
                self.assertEqual(data['protocol_pass'],not fail)


if __name__=='__main__': unittest.main()
