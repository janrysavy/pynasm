"""Run published regression sources through this computer's real NASM."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('checkout', type=Path)
parser.add_argument('modules', nargs='+')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = [str(args.checkout), str(args.checkout / 'tests')]
os.chdir(args.checkout)
from pynasm import Assembler, AssemblyError

native = Path(os.environ['NASM'])
version = subprocess.check_output([str(native), '-v'], text=True).strip()
if not version.startswith('NASM version 3.02 '):
    raise RuntimeError(version)
original = Assembler.assemble
cases = {}
calls = 0

def checked(self, source, *, filename='<string>'):
    global calls
    if self.compatibility != 'nasm3':
        return original(self, source, filename=filename)
    error = None
    try:
        actual = original(self, source, filename=filename)
    except AssemblyError as exc:
        error, actual = exc, None
    normalized = re.sub(r'(?im)^(\s*cpu\s+)8088\b', r'\g<1>8086', source)
    descriptor = (source, self.optimize, str(filename), tuple(map(str, self.include_paths)),
                  tuple(sorted(self.defines.items())), tuple(map(str, self.preincludes)))
    key = hashlib.sha256(repr(descriptor).encode()).hexdigest()
    # All reused cases in this campaign are source-only; include-backed inputs
    # are intentionally not cached because their files can change during tests.
    cached = cases.get(key) if not self.include_paths and not self.preincludes else None
    if cached is None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inp, out = root / 'case.asm', root / 'case.bin'
            inp.write_bytes(normalized.encode('latin1'))
            argv = [str(native), '-f', 'bin', f'-O{self.optimize}', '-o', str(out)]
            for include in [Path(filename).parent, args.checkout, *self.include_paths]:
                argv += ['-I', str(include.resolve()) + os.sep]
            for name, value in self.defines.items():
                argv += ['-D', f'{name}={value}']
            for preinclude in self.preincludes:
                argv += ['-p', str(preinclude)]
            result = subprocess.run([*argv, str(inp)], capture_output=True, timeout=5)
            if result.returncode not in (0, 1):
                raise RuntimeError('native NASM failed: ' + repr(result))
            if result.returncode == 1 and not re.search(rb'(?:error|fatal):', result.stderr):
                raise RuntimeError('native failure is not an assembly rejection')
            expected = out.read_bytes() if result.returncode == 0 else None
            cached = {'source': source, 'optimization': self.optimize,
                      'native_hex': None if expected is None else expected.hex(),
                      'native_stderr': result.stderr.decode('utf-8', errors='replace')}
    expected = None if cached['native_hex'] is None else bytes.fromhex(cached['native_hex'])
    cached['actual_hex'] = None if actual is None else actual.hex()
    cached['actual_error'] = None if error is None else str(error)
    cached['match'] = actual == expected
    cases[key] = cached
    calls += 1
    if actual != expected:
        raise AssertionError(f'native NASM discrepancy {key}: {source!r}; '
                             f'actual={None if actual is None else actual[:24].hex()} '
                             f'native={None if expected is None else expected[:24].hex()}')
    if error:
        raise error
    return actual

Assembler.assemble = checked
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name)
                           for name in args.modules)
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {'checkout': str(args.checkout), 'head': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'native_version': version,
    'native_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
    'modules': args.modules, 'test_methods': result.testsRun, 'calls': calls,
    'unique_cases': len(cases), 'accepted': sum(c['native_hex'] is not None for c in cases.values()),
    'rejected': sum(c['native_hex'] is None for c in cases.values()),
    'passed': result.wasSuccessful(), 'cases': cases}
with gzip.GzipFile(str(args.out), 'wb', mtime=0) as stream:
    stream.write(json.dumps(report, sort_keys=True).encode())
print('LIVE_NATIVE_REGRESSIONS', {k:v for k,v in report.items() if k != 'cases'})
sys.exit(0 if result.wasSuccessful() else 1)
