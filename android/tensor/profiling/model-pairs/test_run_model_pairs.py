"""Offline validation; no ADB or phone access."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('model_pairs',HERE/'run_model_pairs.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PairRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        self.profile=self.root/'profile.py'
        self.profile.write_text('# test fixture only\n')
        self.argv=['--serial','TEST-DEVICE','--remote-dir','/data/local/tmp/test',
            '--model-a','a.tflite','--sha-a','a'*64,'--model-b','b.tflite','--sha-b','b'*64,
            '--output',str(self.root/'results'),'--profile',str(self.profile)]

    def args(self,*extra):
        return runner.parser().parse_args(self.argv+list(extra))

    def test_default_profiler_points_to_parent_profiling_directory(self):
        args=runner.parser().parse_args(self.argv[:-2])
        self.assertEqual(args.profile,HERE.parent/'profile.py')
        self.assertTrue(args.profile.is_file())

    def test_default_balanced_reproducible_plan(self):
        a=self.args()
        runner.validate(a)
        first=runner.make_plan(a)
        self.assertEqual(first,runner.make_plan(a))
        self.assertEqual(first['order'].count('AB'),3)
        self.assertEqual(first['order'].count('BA'),3)
        self.assertEqual(len({r['name'] for r in first['runs']}),12)
        self.assertEqual((first['frames'],first['warmups'],first['mode']),(600,20,5))
        self.assertEqual(first['native_input_seed'],17)
        self.assertEqual(first['seed'],20261017)

    def test_order_is_balanced_for_all_allowed_pair_counts(self):
        for count in range(2,25,2):
            a=self.args('--pairs',str(count))
            runner.validate(a)
            plan=runner.make_plan(a)
            self.assertEqual(plan['order'].count('AB'),count//2)
            self.assertEqual(plan['order'].count('BA'),count//2)
            for pair in range(count):
                self.assertEqual({r['variant'] for r in plan['runs'] if r['pair']==pair},{'A','B'})

    def test_rejects_unsafe_names_paths_hashes_and_counts(self):
        bad=[('--model-a','../a.tflite'),('--model-b','--help'),('--prefix','x;echo'),
             ('--model-a','a$(id)'),('--remote-dir','/data/local/tmp/../data'),
             ('--remote-dir','/data/local/tmp/sub/child'),('--remote-dir','/sdcard/test'),
             ('--serial',''),('--serial','-s'),('--serial','bad serial'),
             ('--sha-a','a'*63),('--sha-b','z'*64),('--pairs','3'),('--pairs','0'),
             ('--pairs','26'),('--frames','9'),('--frames','12001')]
        for option,value in bad:
            with self.subTest(option=option,value=value),self.assertRaises(ValueError):
                runner.validate(self.args(option + '=' + value))

    def test_hardware_metric_must_be_available_finite_and_positive(self):
        for value in (None, float('nan'), float('inf'), 0, -1, '27.0'):
            self.assertFalse(runner.complete_hardware_metric({'hardware_mean_ms':value}))
        self.assertTrue(runner.complete_hardware_metric({'hardware_mean_ms':27.0}))

    def test_existing_output_refused(self):
        (self.root/'results').mkdir()
        with self.assertRaisesRegex(ValueError,'existing'):
            runner.validate(self.args())

    def test_missing_profiler_refused(self):
        self.profile.unlink()
        with self.assertRaisesRegex(ValueError,'missing'):
            runner.validate(self.args())

    def test_remote_hash_parser_requires_exact_file(self):
        digest='A'*64
        path='/data/local/tmp/test/a.tflite'
        self.assertEqual(runner.parse_remote_hash(digest+'  '+path+'\n',path),'a'*64)
        for value in [digest+'  '+path+'.bad',digest+'  '+path+'\nextra','not-a-sha '+path]:
            with self.assertRaises(RuntimeError):
                runner.parse_remote_hash(value,path)

    def test_output_comparison_rejects_missing_and_changed(self):
        self.assertFalse(runner.matching_outputs([]))
        self.assertFalse(runner.matching_outputs([{'output_sha256':{}}]))
        one={'output_sha256':{'output-0.bin':'a'*64}}
        self.assertTrue(runner.matching_outputs([one,one]))
        self.assertFalse(runner.matching_outputs([one,{'output_sha256':{'output-0.bin':'b'*64}}]))

    def fake_execution(self, cleanup_fails=False):
        a=self.args('--pairs','2','--frames','10')
        runner.validate(a)
        plan=runner.make_plan(a)
        a.output.mkdir()
        fake=SimpleNamespace()
        def adb(*args,**kwargs):
            if args==('get-state',):
                return 'device'
            if args==('shell','dumpsys battery'):
                return 'temperature: 300'
            if args==('shell','dumpsys thermalservice'):
                return 'Thermal Status: 0'
            command=args[1] if len(args)>1 else ''
            if command.startswith('readlink -f '):
                return a.remote_dir
            if command.startswith('sha256sum '):
                path=command.split()[-1]
                digest='a'*64 if path.endswith('/a.tflite') else 'b'*64 if path.endswith('/b.tflite') else 'c'*64
                return digest+'  '+path
            if cleanup_fails and command.startswith('rmdir '):
                raise RuntimeError('simulated cleanup failure')
            return ''
        def run(name,model,mode,frames,copy_inputs,metrics):
            fake.adb('shell','dumpsys battery')
            fake.adb('shell','dumpsys thermalservice')
            return {'name':name,'frames':frames,'hardware_mean_ms':27.0,
                    'output_sha256':{'output-0.bin':'d'*64}}
        fake.adb,fake.run=adb,run
        spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
        with mock.patch.object(runner.importlib.util,'spec_from_file_location',return_value=spec), \
             mock.patch.object(runner.importlib.util,'module_from_spec',return_value=fake):
            if cleanup_fails:
                with self.assertRaisesRegex(RuntimeError,'cleanup failure'):
                    runner.execute(a,plan)
            else:
                runner.execute(a,plan)
        return a.output

    def test_offline_execution_retains_telemetry_and_matching_results(self):
        output=self.fake_execution()
        results=json.loads((output/'results.json').read_text())
        self.assertEqual(len(results),4)
        self.assertTrue(runner.matching_outputs(results))
        self.assertEqual(len((output/'raw-health.jsonl').read_text().splitlines()),8)
        self.assertFalse((output/'failure.json').exists())
        self.assertFalse(json.loads((output/'completion.json').read_text())['remote_runner_lock_retained'])

    def test_cleanup_failure_preserves_checkpoint_without_success_results(self):
        output=self.fake_execution(cleanup_fails=True)
        self.assertFalse((output/'results.json').exists())
        self.assertEqual(len(json.loads((output/'checkpoint.json').read_text())),4)
        failure=json.loads((output/'failure.json').read_text())
        self.assertTrue(failure['remote_runner_lock_retained'])
        self.assertEqual(failure['completed_runs'],4)

    def test_plan_only_does_not_contact_adb_or_import_profiler(self):
        self.profile.write_text("raise AssertionError('profile must not execute')\n")
        with mock.patch.object(runner,'execute',side_effect=AssertionError('ADB must not execute')):
            self.assertEqual(runner.main(self.argv+['--plan-only']),0)
        plan=json.loads((self.root/'results/plan.json').read_text())
        self.assertEqual(len(plan['runs']),12)
        self.assertEqual(list((self.root/'results').iterdir()),[self.root/'results/plan.json'])


if __name__=='__main__':
    unittest.main()

