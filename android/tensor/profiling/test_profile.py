"""Health stops and process ownership must work without a physical phone."""
import importlib.util
import pathlib
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('tensor_profile',pathlib.Path(__file__).with_name('profile.py'))
profile=importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)

class ProfileGuards(unittest.TestCase):
    def test_rejects_missing_or_unsafe_health(self):
        for battery,thermal in [('temperature: 430','Thermal Status: 0'),
                                ('temperature: 250','Thermal Status: 3'),
                                ('temperature: 250','unavailable'),
                                ('unavailable','Thermal Status: 0')]:
            with self.subTest(battery=battery,thermal=thermal), patch.object(profile,'adb',side_effect=[battery,thermal]):
                with self.assertRaises(RuntimeError): profile.health()

    def test_accepts_below_threshold(self):
        with patch.object(profile,'adb',side_effect=['temperature: 429','Thermal Status: 2']):
            self.assertEqual(profile.health()['battery_c'],42.9)

    def test_does_not_signal_a_finished_process(self):
        proc=Mock();proc.poll.return_value=2
        with patch.object(profile,'adb') as adb:
            profile.stop_owned(proc,'failed')
            adb.assert_not_called()

    def test_does_not_signal_unrelated_reused_pid(self):
        proc=Mock();proc.poll.return_value=None
        with patch.object(profile,'adb',side_effect=['1234','another-process']) as adb:
            profile.stop_owned(proc,'owned')
            self.assertEqual(adb.call_count,2)
            proc.terminate.assert_called_once()

    def test_signals_only_owned_benchmark(self):
        proc=Mock();proc.poll.return_value=None
        with patch.object(profile,'adb',side_effect=['1234','tensor-bench','']) as adb:
            profile.stop_owned(proc,'owned')
            self.assertEqual(adb.call_args.args,('shell','kill','-TERM','1234'))
            proc.terminate.assert_called_once()

if __name__=='__main__': unittest.main()
