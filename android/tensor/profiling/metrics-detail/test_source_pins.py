"""Check checkout-independent source pins without an NDK, SDK or phone."""
import hashlib
import importlib.util
import pathlib
import tempfile
import unittest

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('metrics_detail_build', HERE/'build.py')
build=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class SourcePins(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        self.original_pins=build.SOURCE_PINS
        self.addCleanup(setattr,build,'SOURCE_PINS',self.original_pins)
        # A tiny bridge fixture verifies the same gate without redistributing
        # the externally supplied CLiteRt tree. Real profiler sources stay pinned.
        self.data={'bridge':b'// bridge fixture\nint value = 5;\n',
                   'profiler':(HERE.parent/'native_profile.c').read_bytes().replace(b'\r\n',b'\n'),
                   'metrics':(HERE.parent/'metrics.inc').read_bytes().replace(b'\r\n',b'\n')}
        build.SOURCE_PINS={**build.SOURCE_PINS,'bridge':hashlib.sha256(self.data['bridge']).hexdigest()}
        self.paths={role:self.root/(role+'.c') for role in self.data}
    def write(self, crlf):
        for role,data in self.data.items():self.paths[role].write_bytes(data.replace(b'\n',b'\r\n') if crlf else data)
    def test_real_profiler_pins_are_exact(self):
        for role in ('profiler','metrics'):
            self.assertEqual(hashlib.sha256(self.data[role]).hexdigest(),self.original_pins[role])
    def test_lf_passes(self):
        self.write(False);observed=build.validate_source_pins(self.paths)
        for role in self.data:self.assertEqual(observed[role]['raw_sha256'],observed[role]['lf_normalized_sha256'])
    def test_crlf_passes_and_retains_raw_provenance(self):
        self.write(True);observed=build.validate_source_pins(self.paths)
        for role in self.data:
            self.assertEqual(observed[role]['lf_normalized_sha256'],build.SOURCE_PINS[role])
            self.assertNotEqual(observed[role]['raw_sha256'],observed[role]['lf_normalized_sha256'])
    def test_equivalent_forms_have_equal_pins(self):
        self.write(False);lf=build.validate_source_pins(self.paths)
        self.write(True);crlf=build.validate_source_pins(self.paths)
        self.assertEqual({k:v['lf_normalized_sha256'] for k,v in lf.items()},{k:v['lf_normalized_sha256'] for k,v in crlf.items()})
    def test_semantic_drift_is_rejected_for_every_role(self):
        for role in self.data:
            with self.subTest(role=role):
                self.write(False);self.paths[role].write_bytes(self.paths[role].read_bytes()+b'int changed;\n')
                with self.assertRaises(ValueError):build.validate_source_pins(self.paths)
    def test_other_whitespace_changes_are_rejected(self):
        self.write(False);self.paths['profiler'].write_bytes(self.data['profiler']+b' ')
        with self.assertRaises(ValueError):build.validate_source_pins(self.paths)
    def test_bare_carriage_return_is_not_normalized(self):
        self.write(False);self.paths['metrics'].write_bytes(self.data['metrics'].replace(b'\n',b'\r'))
        with self.assertRaises(ValueError):build.validate_source_pins(self.paths)
    def test_buffer_tools_header_pin_accepts_both_checkout_forms(self):
        spec=importlib.util.spec_from_file_location('buffer_tools_build',HERE.parent/'buffer-tools/build.py')
        buffers=importlib.util.module_from_spec(spec);spec.loader.exec_module(buffers)
        header=(HERE.parent/'litert_metrics.h').read_bytes().replace(b'\r\n',b'\n')
        path=self.root/'metrics.h'
        for data in (header,header.replace(b'\n',b'\r\n')):
            path.write_bytes(data);self.assertEqual(buffers.normalized_sha(path),buffers.METRICS_SHA256)
        path.write_bytes(header+b' ')
        self.assertNotEqual(buffers.normalized_sha(path),buffers.METRICS_SHA256)

    def test_missing_source_is_rejected(self):
        self.write(False);self.paths['bridge'].unlink()
        with self.assertRaises(ValueError):build.validate_source_pins(self.paths)

if __name__=='__main__':unittest.main()
