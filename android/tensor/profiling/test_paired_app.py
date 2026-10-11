"""A failed experiment must restore its APK and preserve unowned forwards."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import paired_app


class PairedAppTests(unittest.TestCase):
    def run_case(self, conflict=False, rollback_failure=False, order=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            apks=[]
            for name in ('control.apk','candidate.apk','rollback.apk'):
                path=root/name;path.write_bytes(name.encode());apks.append(path)
            calls=[]
            def run(command, **kwargs):
                args=command[3:];calls.append(args)
                output=''
                if args==['get-state']: output='device'
                elif args==['shell','dumpsys','battery']: output='temperature: 280'
                elif args==['shell','dumpsys','thermalservice']: output='Thermal Status: 0'
                elif args==['shell','ss','-ltn']: output='LISTEN 0 0 *:5599'
                elif args==['forward','--list'] and conflict: output='another-device tcp:5599 tcp:5599'
                elif args[:2]==['install','-r'] and Path(args[2])==apks[2] and rollback_failure:
                    raise subprocess.CalledProcessError(1,command)
                return types.SimpleNamespace(stdout=output)
            argv=['paired_app','--serial','fixture','--control-apk',str(apks[0]),
                '--candidate-apk',str(apks[1]),'--rollback-apk',str(apks[2]),
                '--rollback-sha256',hashlib.sha256(apks[2].read_bytes()).hexdigest(),
                '--client-path',str(root),'--source-sha256','0'*64,'--source-bytes','1',
                '--output',str(root/'results')]
            if order is not None: argv += ['--order',order]
            with patch.object(sys,'argv',argv), patch.object(paired_app.subprocess,'run',side_effect=run), \
                 patch.object(paired_app.subprocess,'Popen',side_effect=RuntimeError('fixture benchmark failure')), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError) as error:
                paired_app.main()
            return calls,json.loads((root/'results/manifest.json').read_text()),str(error.exception)

    def test_benchmark_failure_restores_and_removes_owned_forward(self):
        calls,manifest,_=self.run_case()
        installs=[c for c in calls if c[:2]==['install','-r']]
        self.assertEqual(len(installs),2)
        self.assertEqual(Path(installs[-1][2]).name,'rollback.apk')
        self.assertIn(['forward','--remove','tcp:5599'],calls)
        self.assertIn('reinstalled',manifest['rollback'])

    def test_preserves_existing_forward_and_avoids_install(self):
        calls,manifest,_=self.run_case(conflict=True)
        self.assertFalse(any(c[0]=='install' or c[:2]==['forward','--remove'] for c in calls))
        self.assertIn('already forwarded',manifest['failures'][0])

    def test_rollback_failure_is_not_success(self):
        _,manifest,error=self.run_case(rollback_failure=True)
        self.assertTrue(manifest['rollback'].startswith('FAILED:'))
        self.assertIn('FAILED:',error)

    def test_explicit_tail_order_starts_with_candidate(self):
        calls,manifest,_=self.run_case(order='BA')
        first=next(c for c in calls if c[:2]==['install','-r'])
        self.assertEqual(Path(first[2]).name,'candidate.apk')
        self.assertEqual(manifest['order'],'BA')
        self.assertEqual(manifest['pairs'],1)

    def test_invalid_pair_order_is_rejected_before_device_access(self):
        argv=['paired_app','--serial','fixture','--control-apk','absent','--candidate-apk','absent',
              '--rollback-apk','absent','--rollback-sha256','0'*64,'--client-path','absent',
              '--source-sha256','0'*64,'--source-bytes','1','--output','absent','--order','AA']
        with patch.object(sys,'argv',argv),patch.object(paired_app.subprocess,'run') as device, \
             contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            paired_app.main()
        device.assert_not_called()


if __name__=='__main__': unittest.main()
