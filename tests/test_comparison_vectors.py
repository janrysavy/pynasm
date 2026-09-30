"""Relational expression vectors, pinned to NASM 3.02 asm/eval.c rexp3().

Oracle source: 4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065.
The declared differences below are symbolic: None means uncancelled section
or register terms, not an unknown numeric address. A live oracle verifies
all generated expectations; CI replays them without an external assembler.
"""
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version


OPS = ('=', '==', '!=', '<>', '<', '<=', '>', '>=', '<=>')


def result(op, difference):
    if op in ('=', '=='):
        return int(difference == 0)
    if op in ('!=', '<>'):
        return int(difference != 0)
    if difference is None:
        return None
    # The pinned NASM revision represents a negative <=> result as unknown;
    # these non-critical output contexts emit its zero placeholder.
    if op == '<=>':
        return int(difference > 0)
    return int({'<': difference < 0, '<=': difference <= 0,
                '>': difference > 0, '>=': difference >= 0}[op])


def cases():
    ordinary = [
        ('start', '0', None), ('end', '1', None),
        ('start', 'start', 0), ('start+1', 'end', 0),
        ('end', 'start', 1), ('start', 'end', -1),
        ('end-start', '1', 0), ('2*start', 'start', None),
        ('2*start', '2*start', 0), ('$', 'end', 0), ('$$', 'start', 0),
        ('0xffffffffffffffff', '-1', 0),
        ('0x7fffffffffffffff', '-1', -0x8000000000000000),
    ]
    sections = [
        ('a', 'b', None), ('a-b', '0', None),
        ('a-b', 'a-b', 0), ('(a-b)+b', 'a', 0),
        ('a-b', 'b-a', None), ('(a-b)-(a-b)', '0', 0),
    ]
    registers = [
        ('bx', 'bx', 0), ('bx', 'si', None),
        ('bx+1', 'bx', 1), ('bx', 'bx+1', -1),
        ('bx+start', 'bx', None), ('bx+start', 'si+start', None),
        ('bx+start', 'bx+start', 0), ('bp+si', 'si+bp', 0),
        ('bx+start', 'bx+end', -1),
    ]
    for group, prefix, pairs, uses in (
        ('labels', 'start:nop\nend:\n', ordinary,
         (('dw ({})', ''), ('mov ax, ({})', 'b8'), ('mov ax, [({})]', 'a1'),
          ('value equ ({})\ndw value', ''))),
        ('sections', 'section .a start=0 vstart=0\na:nop\n'
         'section .b start=1 vstart=0\nb:\n', sections,
         (('dw ({})', ''), ('mov ax, [({})]', 'a1'))),
        ('registers', 'start:nop\nend:\n', registers,
         (('mov ax, [({})]', 'a1'),)),
    ):
        for left, right, difference in pairs:
            for op in OPS:
                expression = f'({left}) {op} ({right})'
                value = result(op, difference)
                for use, opcode in uses:
                    source = 'cpu 8086\nbits 16\n' + prefix + use.format(expression) + '\n'
                    expected = None if value is None else bytes.fromhex(
                        '90' + opcode + ('0100' if value else '0000'))
                    yield group, source, expected
    for expression, expected in (
        ('later = 0', '000090'), ('later != 0', '010090'),
        ('later = later', '010090'), ('later < 0', None),
        ('missing = 0', None),
    ):
        yield 'forward', f'cpu 8086\ndw {expression}\nlater:nop\n', (
            None if expected is None else bytes.fromhex(expected))


class ComparisonVectorTests(unittest.TestCase):
    def test_comparison_vectors(self):
        for level in (0, 1, 9):
            for cpu in ('8086', '8088'):
                assembler = Assembler(compatibility='nasm3', optimize=level)
                for group, source, expected in cases():
                    with self.subTest(level=level, cpu=cpu, group=group, source=source):
                        source = source.replace('cpu 8086', f'cpu {cpu}')
                        if expected is None:
                            with self.assertRaises(AssemblyError):
                                assembler.assemble(source)
                        else:
                            self.assertEqual(assembler.assemble(source), expected)
                self.assertEqual(assembler.assemble('nop'), b'\x90')

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_pinned_reference(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for group, source, expected in cases():
            for level in (0, 1, 9):
                with self.subTest(level=level, group=group, source=source):
                    self.assertEqual(reference(native, source, level), expected)
