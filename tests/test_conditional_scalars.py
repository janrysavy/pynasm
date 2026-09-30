"""NASM 3.02 asm/eval.c: the condition of ?: must be scalar.

Oracle source: 4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065.
Only the NASM 3 profile is changed; 8088 is checked against NASM's 8086.
"""
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version


PRELUDE = 'bits 16\norg 0x100\nstart: db 0\nend:\n'
REJECTED = [
    PRELUDE + use.format(condition=condition) + '\n'
    for condition in ('start', '$', '$$', '2 * start', '-start')
    for use in ('dw ({condition}) ? 7 : 9',
                'mov ax, ({condition}) ? 7 : 9',
                'mov ax, [({condition}) ? bx : si]')
] + [
    # Total relocation coefficient zero is not sufficient: distinct bases
    # remain in a difference between labels from different sections.
    'section .text\na: nop\nsection .data\nb:\n' + use + '\n'
    for use in ('dw (b-a) ? 7 : 9', 'mov ax, [(b-a) ? bx : si]')
] + [
    # An initially unknown condition must be checked when it resolves.
    'dw target ? 7 : 9\ntarget: nop\n',
    'mov ax, [target ? bx : si]\ntarget: nop\n',
]
ACCEPTED = [
    ('dw 0 ? 7 : 9\n', '0900'),
    ('dw 1 ? 7 : 9\n', '0700'),
    ('dw -1 ? 7 : 9\n', '0700'),
    ('dw (1 ? 0 : 1) ? 7 : 9\n', '0900'),
    (PRELUDE + 'dw (end-start) ? 7 : 9\n', '000700'),
    (PRELUDE + 'dw (start-start) ? 7 : 9\n', '000900'),
    (PRELUDE + 'mov ax, [(end-start) ? bx : si]\n', '008b07'),
    ('mov ax, [0 ? bx : si]\n', '8b04'),
    ('dw choice ? 7 : 9\nchoice equ 1\n', '0700'),
    ('mov ax, [choice ? bx : si]\nchoice equ 1\n', '8b07'),
    # The selected value need not be scalar, only the condition does.
    ('start: nop\ndw 1 ? start : 123\n', '900000'),
    ('section .text\na:nop\nsection .data\nb:\n'
     'dw ((b-a)-(b-a)) ? 7 : 9\n', '900000000900'),
]


class ConditionalScalarTests(unittest.TestCase):
    def test_reject_relocatable_conditions(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                assembler = Assembler(compatibility='nasm3', optimize=level)
                for source in REJECTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        with self.assertRaises(AssemblyError):
                            assembler.assemble(f'cpu {cpu}\n' + source)
                self.assertEqual(assembler.assemble(f'cpu {cpu}\nnop\n'), b'\x90')

    def test_accept_scalar_conditions_and_relocatable_results(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source, expected in ACCEPTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        actual = Assembler(compatibility='nasm3', optimize=level).assemble(
                            f'cpu {cpu}\n' + source)
                        self.assertEqual(actual.hex(), expected)

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_pinned_reference(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for source, expected in [(s, None) for s in REJECTED] + ACCEPTED:
            for level in (0, 1, 9):
                with self.subTest(source=source, level=level):
                    result = reference(native, 'cpu 8086\n' + source, level)
                    self.assertEqual(None if result is None else result.hex(), expected)
