"""TIMES counts must be scalar, even when a relocatable offset is zero.

Oracle: NASM 3.02, source 4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065.
"""
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version


REJECTED = [
    'times $ db 0\n',
    'times $$ db 0\n',
    'label: times label db 0\n',
    'db 0\nlabel: times label db 0\n',
    'org 0x100\nlabel: times label db 0\n',
    'label: times (label+1) dw 0\n',
    'label: times (1-label) db 0\n',
    'alias equ label\nlabel: times alias db 0\n',
    'section .text\na: db 0\nsection .data\nb: times (b-a) db 0\n',
    'section .text\na: db 0\nsection .data\nb: times ((b-a)*2) db 0\n',
    'times missing db 0\n',
    'times -1 db 0\n',
]
ACCEPTED = [
    ('times 0 db 0\nnop\n', '90'),
    ('times 2 db 0x41\n', '4141'),
    ('times 2 dw 0x1234\n', '34123412'),
    ('a: db 0\nb: times (b-a) db 1\n', '0001'),
    ('org 0x100\na: db 0\nb: times (b-a) db 1\n', '0001'),
    ('a: times (a-a) db 1\nnop\n', '90'),
    ('a: times ($-$$) db 1\nnop\n', '90'),
    ('count equ 2\ntimes count db 0x42\n', '4242'),
    ('absolute 2\ncount:\nsection .text\ntimes count db 0x42\n', '4242'),
    ('section .text\na: db 0\nsection .data\nb:\n'
     'times ((b-a)-(b-a)+1) db 1\n', '0000000001'),
]


class TimesScalarCountTests(unittest.TestCase):
    def test_reject_non_scalar_counts(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                assembler = Assembler(compatibility='nasm3', optimize=level)
                for source in REJECTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        with self.assertRaises(AssemblyError):
                            assembler.assemble(f'cpu {cpu}\n' + source)
                        self.assertEqual(assembler.listing, ())
                self.assertEqual(assembler.assemble(f'cpu {cpu}\nnop\n'), b'\x90')

    def test_scalar_counts_keep_exact_bytes(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source, expected in ACCEPTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        actual = Assembler(compatibility='nasm3', optimize=level).assemble(
                            f'cpu {cpu}\n' + source)
                        self.assertEqual(actual.hex(), expected)

    def test_legacy_profile_is_unchanged(self):
        for cpu in ('8086', '8088'):
            source = f'cpu {cpu}\ndb 0\nlabel: times label db 1\n'
            self.assertEqual(Assembler(compatibility='nasm09839').assemble(source), b'\x00\x01')

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_pinned_reference(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for source, expected in [(s, None) for s in REJECTED] + ACCEPTED:
            for level in (0, 1, 9):
                with self.subTest(source=source, level=level):
                    result = reference(native, 'cpu 8086\n' + source, level)
                    self.assertEqual(None if result is None else result.hex(), expected)


if __name__ == '__main__':
    unittest.main()
