"""Scalar DUP/RES counts, pinned against NASM 3.02 (4a56d66ed962)."""
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version


REJECTED = [
    'a: db a dup(1)\n',
    'a: db 0\ndb a dup(1)\n',
    'org 0x100\na: dw a dup(1)\n',
    'db $ dup(1)\n',
    'dw $$ dup(1)\n',
    'a: dq (a+1) dup(1)\n',
    'a: db word (a dup(1))\n',
    'a: db %(a dup(1))\n',
    'section .text\na:db 0\nsection .data\nb:db (b-a) dup(1)\n',
]
REJECTED += [
    f'section .text\na:db 0\nsection .data\nb:{directive} (b-a)\n'
    for directive in ('resb', 'resw', 'resd', 'resq', 'rest', 'reso', 'resy', 'resz')
]
ACCEPTED = [
    ('a:db 0\nb:db (b-a) dup(2)\n', '0002'),
    ('org 0x100\na:db 0\nb:dw (b-a) dup(0x1234)\n', '003412'),
    ('a:db (a-a) dup(1)\nnop\n', '90'),
    ('count equ 2\ndb count dup(3)\n', '0303'),
    ('absolute 2\ncount:\nsection .text\ndb count dup(3)\n', '0303'),
    ('a:db 0\nb:resb b-a\n', '0000'),
    ('a:db 0\nb:resw b-a\n', '000000'),
    ('section .text\na:db 0\nsection .data\nb:\n'
     'db ((b-a)-(b-a)+1) dup(2)\n', '0000000002'),
    ('section .text\na:db 0\nsection .data\nb:\n'
     'resb ((b-a)-(b-a)+1)\ndb 2\n', '000000000002'),
    ('resb count\ncount equ 2\ndb 2\n', '000002'),
]


class DataScalarCountTests(unittest.TestCase):
    def test_reject_non_scalar_counts(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source in REJECTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        with self.assertRaises(AssemblyError):
                            Assembler(compatibility='nasm3', optimize=level).assemble(
                                f'cpu {cpu}\n' + source)

    def test_scalar_counts_keep_exact_bytes(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source, expected in ACCEPTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        actual = Assembler(compatibility='nasm3', optimize=level).assemble(
                            f'cpu {cpu}\n' + source)
                        self.assertEqual(actual.hex(), expected)

    def test_historical_dup_behavior_is_unchanged(self):
        self.assertEqual(Assembler(compatibility='nasm09839').assemble(
            'db 0\na:db a dup(1)\n'), b'\x00\x01')

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
