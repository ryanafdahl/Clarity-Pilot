import json,pathlib,tempfile,unittest
from wake_analysis import analyze

class WakeAnalysisTests(unittest.TestCase):
    def fixture(self,root,censor=False,different=False):
        manifest={'order':'ABBA','traced':False,'failures':[], 'apk_sha256':{},'rollback':'fixture','runs':[]}
        for index,variant in enumerate('ABBA'):
            name=f'{index}-{variant}'
            count=299 if censor and index==1 else 300
            frames=[{'frame_id':i,'warmup':i<100,'server_total_ms':35.1 if variant=='A' else 35.0,
                     'output_sha256':f'fixture-{i}' if not different or index!=1 else 'different'} for i in range(count)]
            result={'measured_frames':count-100,'failures':['100-frame p95 timing limit reached; test stopped'],
                    'wake_stimulus':{'command_completed':True,'command_start_monotonic_s':1.,'command_end_monotonic_s':1.1}}
            (root/(name+'.json')).write_text(json.dumps(result))
            (root/(name+'-frames.json')).write_text(json.dumps({'frames':frames}))
            manifest['runs'].append({'run':index+1,'variant':variant,'result':name+'.json','before':{},'after':{}})
        (root/'manifest.json').write_text(json.dumps(manifest))

    def test_small_gain_and_stops_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.fixture(root)
            result=analyze(root)
            self.assertAlmostEqual(result['paired']['mean_ms']['control_minus_candidate_ms'],.1)
            self.assertEqual(result['A']['timing_stops'],2)
            self.assertEqual(result['B']['timing_stops'],2)

    def test_censored_window_has_no_uncensored_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.fixture(root,censor=True)
            result=analyze(root)
            self.assertEqual(result['censored_trials'],1)
            self.assertEqual(result['paired'],{})
            self.assertIn('primary_unavailable',result)

    def test_output_change_prevents_gain_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.fixture(root,different=True)
            with self.assertRaisesRegex(ValueError,'Output hashes differ'):analyze(root)

if __name__=='__main__':unittest.main()
