import contextlib
import hashlib
import importlib.metadata
import io
import json
import pathlib
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

# Exercise the compiler helper exported in the current support patch, so these
# fixtures cannot silently drift onto a separate copy of the production tool.
SUPPORT = pathlib.Path(__file__).resolve().parents[1] / 'tensor-support.patch'
PATH = 'android/scripts/compile-tensor.py'
text = SUPPORT.read_text()
marker = 'diff --git a/' + PATH + ' b/' + PATH + '\n'
block = text.split(marker, 1)[1].split('\ndiff --git ', 1)[0]
assert 'new file mode ' in block
source = ''.join(line[1:] for line in block.splitlines(True)
                 if line.startswith('+') and not line.startswith('+++'))
SCRIPT_DIRECTORY = tempfile.TemporaryDirectory(prefix='jetlink-compiler-fixtures-')
SCRIPT = pathlib.Path(SCRIPT_DIRECTORY.name) / 'compile-tensor.py'
SCRIPT.write_text(source)



def digest(data):
    return hashlib.sha256(data).hexdigest()


def elf(*, executable=True, bits=64, endian='little'):
    # Header metadata only; fixtures never execute SDK files.
    header = bytearray(32)
    header[:4] = b'\x7fELF'
    header[4:7] = bytes([2 if bits == 64 else 1, 1 if endian == 'little' else 2, 1])
    header[16:18] = (3).to_bytes(2, endian)
    header[24:32 if bits == 64 else 28] = (0x1234 if executable else 0).to_bytes(8 if bits == 64 else 4, endian)
    return bytes(header)


class ProvenanceFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.sdk = self.root / 'sdk'
        self.sdk.mkdir()
        self.library_bytes = elf(executable=False) + b'compiler library'
        self.library = self.sdk / 'liblitert_plugin_compiler.so'
        self.library.write_bytes(self.library_bytes)
        self.library.chmod(0o555)
        self.source = self.root / 'original.onnx'
        self.source.write_bytes(b'original ONNX fixture')
        self.converted = self.root / 'converted.tflite'
        self.converted.write_bytes(b'converted TFLite fixture')
        self.calls = []

    def helper(self, name, data=None, mode=0o555):
        path = self.sdk / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(elf() + b'worker' if data is None else data)
        path.chmod(mode)
        return path

    def run_cli(self, *extra):
        class FakeModel:
            def save(self, path, export_only):
                assert export_only is True
                pathlib.Path(path).write_bytes(b'compiled fixture')

        def compile_model(model, **kwargs):
            self.calls.append((model, kwargs))
            return types.SimpleNamespace(failed_backends=[], models=[FakeModel()], compilation_report=lambda: 'fixture report')

        modules = {
            'ai_edge_litert.aot.aot_compile': types.SimpleNamespace(aot_compile=compile_model),
            'ai_edge_litert.aot.vendors.google_tensor.target': types.SimpleNamespace(Target=lambda soc: soc, SocModel=lambda soc: soc),
        }
        args = [str(SCRIPT), '--sdk', str(self.sdk), '--source', str(self.source), '--model', str(self.converted), '--output', str(self.root / 'out'), *extra]
        with patch.dict(sys.modules, modules), patch.object(sys, 'argv', args), patch.object(importlib.metadata, 'version', return_value='2.3.0'), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            runpy.run_path(str(SCRIPT), run_name='__main__')
        manifest = self.root / 'out' / digest(self.source.read_bytes()) / 'manifest.json'
        return json.loads(manifest.read_text())

    def test_old_library_only_sdk_and_exact_keys(self):
        manifest = self.run_cli()
        self.assertEqual(set(manifest), {'source_sha256', 'source_converted_sha256', 'compiled_sha256', 'soc', 'litert', 'sdk_sha256', 'sdk_executables_sha256', 'precision', 'sharding'})
        self.assertEqual(manifest['sdk_executables_sha256'], {})
        self.assertEqual(manifest['sdk_sha256'], digest(self.library_bytes))
        self.assertEqual(manifest['compiled_sha256'], digest(b'compiled fixture'))
        self.assertEqual(manifest['source_sha256'], digest(self.source.read_bytes()))
        self.assertEqual(manifest['source_converted_sha256'], digest(self.converted.read_bytes()))
        self.assertEqual((manifest['soc'], manifest['litert'], manifest['precision'], manifest['sharding']), ('Tensor_G6', '2.3.0', 'half', 'minimal'))
        self.assertEqual(self.calls[0][0], str(self.converted))
        self.assertEqual(self.calls[0][1]['google_tensor_truncation_type'], 'half')
        self.assertEqual(self.calls[0][1]['google_tensor_sharding_intensity'], 'minimal')
        self.assertIs(self.calls[0][1]['keep_going'], False)

    def test_renamed_worker_is_discovered(self):
        worker = self.helper('renamed_backend')
        manifest = self.run_cli()
        self.assertEqual(manifest['sdk_worker'], 'renamed_backend')
        self.assertEqual(manifest['sdk_worker_sha256'], digest(worker.read_bytes()))
        self.assertEqual(manifest['sdk_executables_sha256'], {'renamed_backend': digest(worker.read_bytes())})
        self.assertNotIn(str(self.root), json.dumps(manifest))

    def test_nested_worker_and_shared_library(self):
        self.helper('lib/helper.so', elf(executable=False))
        worker = self.helper('bin/tool', elf(bits=32, endian='big'))
        manifest = self.run_cli('--sdk-worker', 'bin/tool')
        self.assertEqual(manifest['sdk_worker'], 'bin/tool')
        self.assertEqual(manifest['sdk_worker_sha256'], digest(worker.read_bytes()))

    def test_executable_license_and_nonexecutable_file_ignored(self):
        self.helper('licenses.txt', b'copyright license text', mode=0o777)
        self.helper('not-installed-worker', elf(), mode=0o444)
        self.helper('third_party/unsupported_toolchains/bin/clang', elf())
        manifest = self.run_cli()
        self.assertNotIn('sdk_worker_sha256', manifest)
        self.assertEqual(manifest['sdk_executables_sha256'], {})

    def test_script_helper_supported(self):
        worker = self.helper('runner', b'#!/bin/sh\nexec worker-impl\n')
        self.assertEqual(self.run_cli()['sdk_worker_sha256'], digest(worker.read_bytes()))

    def test_multiple_helpers_require_selection_before_compilation(self):
        self.helper('worker-a')
        self.helper('worker-b')
        with self.assertRaises(SystemExit) as error:
            self.run_cli()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.calls, [])

    def test_explicit_worker_records_all_helpers(self):
        self.helper('other-helper')
        worker = self.helper('bin/selected-helper')
        manifest = self.run_cli('--sdk-worker', 'bin/selected-helper')
        self.assertEqual(manifest['sdk_worker'], 'bin/selected-helper')
        self.assertEqual(manifest['sdk_worker_sha256'], digest(worker.read_bytes()))
        self.assertEqual(list(manifest['sdk_executables_sha256']), ['bin/selected-helper', 'other-helper'])

    def test_invalid_explicit_worker_refused(self):
        for value in ['missing', '../original.onnx', 'liblitert_plugin_compiler.so']:
            with self.subTest(worker=value), self.assertRaises(SystemExit):
                self.run_cli('--sdk-worker', value)
        self.assertEqual(self.calls, [])

    def test_converted_graph_changes_without_changing_source(self):
        before = self.run_cli()
        self.converted.write_bytes(b'changed converted graph')
        after = self.run_cli()
        self.assertEqual(before['source_sha256'], after['source_sha256'])
        self.assertNotEqual(before['source_converted_sha256'], after['source_converted_sha256'])
        self.assertEqual(after['source_converted_sha256'], digest(self.converted.read_bytes()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
