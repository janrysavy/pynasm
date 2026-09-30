"""A zero TIMES body is parsed without encoding, file I/O or large allocation.

Reference: NASM 3.02, source 4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065.
"""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version
from pynasm.floatdata import _literal_value

REJECTED_BODIES = [
    'db missing', 'dw missing', 'dt missing', 'db 1/0', 'dw 1,missing',
    'dw 0 dup(missing)', 'db 0 dup(1/0)', 'db word (missing)', 'db %(missing)',
    'db (1+2', 'db -1 dup(0)', 'db unknown dup(0)',
    'mov ax,missing', 'mov ax,[bx+missing]', 'mov word al,missing',
    'mov ax,1/0', 'mov ax,[bx+(1/0)]', 'mov ax,[bx+si+di]',
    'rep mov ax,missing', 'lock add [bx+missing],1',
    'jmp 1:missing', 'jmp missing:1', 'jmp short missing', 'shl ax,missing',
    'int missing', 'resb missing', 'resb 1/0',
    'incbin "nonexistent",missing', 'incbin "nonexistent",1/0', 'incbin missing',
    'org 256', 'bits 32', 'cpu 386', 'section .data', 'absolute 0', 'align 16',
    'fld tword [bx+missing]',
]
ACCEPTED_BODIES = [
    'nop', 'mov ax,bx', 'mov ax,', 'mov ax,bx,dx', 'mov word al,1',
    'mov ax,[ax]', 'mov ax,[bx*2]', 'mov ax,[ax+bx]', 'mov ax,1:2',
    'shl ax,2', 'jmp short $+130', 'resb -1', 'resb $',
    'db "abc"', 'db 1.0', 'dt 1', 'dq 1e99999', 'db byte 1.0',
    'dw 2 dup(0x1234)', 'db 2 dup(3 dup(1),0)', 'db 0x7fffffff dup(0)',
    'resb 0x7fffffff', 'incbin "nonexistent"', 'incbin "nonexistent",0,10',
    'equ 1', 'cs nop', 'times 0 nop',
    # These emit no code; accepting a zero-body token does not enable its ISA.
    'pusha', 'enter 2,0', 'mov eax,1',
]


def source(body):
    return f'times 0 {body}\nnop\n'


class ZeroTimesValidationTests(unittest.TestCase):
    def test_rejected_bodies_are_still_parsed(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                assembler = Assembler(compatibility='nasm3', optimize=level)
                for body in REJECTED_BODIES:
                    with self.subTest(cpu=cpu, level=level, body=body):
                        with self.assertRaises(AssemblyError):
                            assembler.assemble(f'cpu {cpu}\n' + source(body))
                        self.assertEqual(assembler.listing, ())

    def test_zero_bodies_do_not_encode_or_allocate_repeated_output(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for body in ACCEPTED_BODIES:
                    with self.subTest(cpu=cpu, level=level, body=body):
                        assembler = Assembler(compatibility='nasm3', optimize=level)
                        self.assertEqual(assembler.assemble(f'cpu {cpu}\n' + source(body)), b'\x90')
                        self.assertEqual(assembler.listing[1].offset, 0)

    def test_zero_incbin_never_opens_file(self):
        assembler = Assembler(compatibility='nasm3')
        with patch.object(Path, 'is_file', side_effect=AssertionError('INCBIN opened')):
            self.assertEqual(assembler.assemble(source('incbin "nonexistent",0,10')), b'\x90')

    def test_forward_operand_can_resolve(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                program = f'cpu {cpu}\ntimes 0 mov ax,target\ntarget:nop\n'
                self.assertEqual(Assembler(compatibility='nasm3', optimize=level).assemble(program), b'\x90')

    def test_zero_float_returns_before_exponent_arithmetic(self):
        zero = object()
        for literal in ('0e10', '0e-10', '0x0p10', '0x0p-10'):
            with self.subTest(literal=literal):
                # A non-arithmetic sentinel proves the zero path never performs
                # multiplication/division after constructing Fraction(0).
                with patch('pynasm.floatdata.Fraction', return_value=zero):
                    self.assertIs(_literal_value(literal), zero)

    def test_historical_zero_skip_is_unchanged(self):
        self.assertEqual(Assembler(compatibility='nasm09839').assemble(source('db missing')), b'\x90')

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_pinned_reference(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for body in REJECTED_BODIES + ACCEPTED_BODIES:
            expected = None if body in REJECTED_BODIES else b'\x90'
            for level in (0, 1, 9):
                with self.subTest(body=body, level=level):
                    self.assertEqual(reference(native, 'cpu 8086\n' + source(body), level), expected)


if __name__ == '__main__':
    unittest.main()
