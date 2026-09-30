"""First-pass TIMES decisions checked against an independent NASM corpus."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from critical_times_cases import programs
from nasm_reference import reference, verify_version

FIXTURE = Path(__file__).parent / 'fixtures/generated/nasm302_critical_times.json'


class CriticalTimesTests(unittest.TestCase):
    def corpus(self):
        sources = programs()
        pinned = json.loads(FIXTURE.read_text())
        self.assertEqual(len(sources), pinned['programs'])
        self.assertEqual(hashlib.sha256(json.dumps(sources, separators=(',', ':')).encode()).hexdigest(),
                         pinned['source_sha256'])
        self.assertEqual(len(sources), len(pinned['outputs']))
        return sources, pinned

    def test_pinned_first_pass_outcomes(self):
        sources, pinned = self.corpus()
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source, expected in zip(sources, pinned['outputs']):
                    with self.subTest(cpu=cpu, level=level, source=source):
                        assembler = Assembler(compatibility='nasm3', optimize=level)
                        source = source.replace('cpu 8086', 'cpu ' + cpu)
                        if expected is None:
                            with self.assertRaises(AssemblyError):
                                assembler.assemble(source)
                        else:
                            self.assertEqual(assembler.assemble(source).hex(), expected)

    @unittest.skipUnless(os.environ.get('NASM'), 'optional NASM 3.02 oracle')
    def test_live_reference(self):
        sources, pinned = self.corpus()
        native = Path(os.environ['NASM'])
        verify_version(native)
        for level in (0, 1, 9):
            for source, expected in zip(sources, pinned['outputs']):
                with self.subTest(level=level, source=source):
                    output = reference(native, source, level)
                    self.assertEqual(None if output is None else output.hex(), expected)

    def test_legacy_forward_times_remains_available(self):
        self.assertEqual(Assembler(compatibility='nasm09839').assemble(
            'times count db 7\ncount equ 2\n'), b'\x07\x07')

    def test_each_times_prefix_is_checked(self):
        for source in ('times count times 0 nop\ncount equ 2\n',
                       'times 0 times count nop\ncount equ 2\n'):
            with self.assertRaises(AssemblyError):
                Assembler(compatibility='nasm3').assemble(source)


if __name__ == '__main__':
    unittest.main()
