"""Verify guard-stop retention and unconditional restoration without a phone."""
import contextlib, hashlib, io, json, pathlib, sys, tempfile, types, unittest
from unittest.mock import patch
import wake_app

class WakeRunnerTests(unittest.TestCase):
    def exercise(self, failure=None, conflict=False, prewake=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);apks=[];calls=[]
            for name in ('control','candidate','original'):
                path=root/(name+'.apk');path.write_bytes(name.encode());apks.append(path)
            def run(cmd,**kwargs):
                calls.append(cmd)
                if 'benchmark.py' in ' '.join(cmd):
                    result=pathlib.Path(cmd[cmd.index('--output')+1])
                    failures=[failure] if failure else []
                    result.write_text(json.dumps({'measured_frames':100 if prewake else 200,'protocol_pass':not failure,
                        'failures':failures,'wake_stimulus':{} if prewake else {'command_completed':True}}))
                    return types.SimpleNamespace(returncode=1 if failure else 0)
                if cmd[-2:]==['forward','--list']:out='fixture tcp:5599 tcp:5599' if conflict else ''
                elif cmd[-1]=='get-state':out='device'
                elif cmd[-2:]==['ss','-ltn']:out='LISTEN 0.0.0.0:5599'
                else:out='Thermal Status: 0\ntemperature: 290'
                return types.SimpleNamespace(stdout=out,returncode=0)
            argv=['wake_app','--adb','fixture','--serial','fixture',
                  '--control-apk',str(apks[0]),'--candidate-apk',str(apks[1]),'--rollback-apk',str(apks[2]),
                  '--rollback-sha256',hashlib.sha256(apks[2].read_bytes()).hexdigest(),
                  '--client-path',str(root),'--output',str(root/'results'),
                  '--source-sha256','0'*64,'--source-bytes','1','--order','AB',
                  '--candidate-label','sustained performance 4']
            caught=None
            with patch.object(sys,'argv',argv),patch.object(wake_app.subprocess,'run',side_effect=run), \
                 patch.object(wake_app.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                try:wake_app.main()
                except RuntimeError as e:caught=str(e)
            return calls,json.loads((root/'results/manifest.json').read_text()),caught

    def test_timing_stops_remain_failures_and_restore_original(self):
        calls,m,error=self.exercise('100-frame p95 timing limit reached; test stopped')
        self.assertIsNone(error)
        self.assertEqual(len(m['runs']),2)
        self.assertEqual(m['variant_B'],'sustained performance 4')
        self.assertTrue(all(r['failures'] for r in m['runs']))
        installs=[c for c in calls if 'install' in c]
        self.assertEqual([pathlib.Path(c[-1]).name for c in installs],['control.apk','candidate.apk','original.apk'])
        self.assertIn('reinstalled',m['rollback'])

    def test_non_timing_failure_stops_sequence_and_restores(self):
        _,m,error=self.exercise('Thermal stop threshold reached')
        self.assertIn('Non-timing',error)
        self.assertEqual(len(m['runs']),1)
        self.assertIn('reinstalled',m['rollback'])

    def test_existing_forward_is_preserved_without_install(self):
        calls,m,error=self.exercise(conflict=True)
        self.assertIn('already forwarded',error)
        self.assertFalse(any('install' in c or '--remove' in c for c in calls))
        self.assertNotIn('rollback',m)

    def test_pre_wake_timing_stop_is_retained_without_skipping_remaining_trials(self):
        _,m,error=self.exercise('100-frame p95 timing limit reached; test stopped',prewake=True)
        self.assertIsNone(error)
        self.assertEqual(len(m['runs']),2)
        self.assertTrue(all(r['failures'] and r['measured_frames']==100 for r in m['runs']))
        self.assertIn('reinstalled',m['rollback'])

    def test_missing_wake_without_timing_stop_still_aborts(self):
        _,m,error=self.exercise(prewake=True)
        self.assertIn('Incomplete trial',error)
        self.assertEqual(len(m['runs']),1)
        self.assertIn('reinstalled',m['rollback'])

    def test_continuation_requires_exact_unrun_suffix_and_builds(self):
        previous={'order':'ABBA','runs':[{'variant':'A','result':'01-A.json'}],'failures':['health query failed'],
                  'apk_sha256':{'A':'a','B':'b'},'rollback_sha256':'r','traced':False}
        self.assertEqual(wake_app.validate_continuation(previous,'BBA',{'A':'a','B':'b'},'r',False,{'01-A.json'}),1)
        for order,hashes in [('ABBA',{'A':'a','B':'b'}),('BA',{'A':'a','B':'b'}),('BBA',{'A':'a','B':'changed'})]:
            with self.subTest(order=order,hashes=hashes),self.assertRaises(ValueError):
                wake_app.validate_continuation(previous,order,hashes,'r',False,{'01-A.json'})

    def test_continuation_rejects_unrecorded_or_missing_result_files(self):
        previous={'order':'ABBA','runs':[{'variant':'A','result':'01-A.json'}],'failures':['health query failed'],
                  'apk_sha256':{'A':'a','B':'b'},'rollback_sha256':'r','traced':False}
        for saved in (set(),{'01-A.json','02-B.json'}):
            with self.subTest(saved=saved),self.assertRaisesRegex(ValueError,'reconcile orphaned trials'):
                wake_app.validate_continuation(previous,'BBA',{'A':'a','B':'b'},'r',False,saved)

if __name__=='__main__':unittest.main()
