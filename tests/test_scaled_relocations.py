"""8086 scalar multiplication must preserve relocation coefficients."""
import unittest

from pynasm import AssemblyError, assemble
from pynasm.expression import Value, evaluate, evaluate_address


EQUIVALENTS = ('target*1', '1*target', 'target*2-target',
               '3*target-2*target', '2*(target+3)-target-6',
               '-(target*-1)')


class ScaledRelocationTests(unittest.TestCase):
    def test_scaled_forward_branch(self):
        for cpu in ('8086', '8088'):
            for expr in EQUIVALENTS:
                with self.subTest(cpu=cpu, expr=expr):
                    source = (f'cpu {cpu}\njmp {expr}+1\ntimes 126 db 0\n'
                              'align 2,db 0\ntarget:nop\nnop\n')
                    self.assertEqual(assemble(source, optimize=9, compatibility='nasm3'),
                                     b'\xeb\x7f' + bytes(126) + b'\x90\x90')

    def test_relocated_memory_keeps_displacement(self):
        # NASM 3.02 -O0/-O1/-O9: a label retains disp16 even when its value is zero.
        for cpu in ('8086', '8088'):
            for expr in EQUIVALENTS:
                for level in (0, 1, 9):
                    with self.subTest(cpu=cpu, expr=expr, level=level):
                        source = f'cpu {cpu}\ntarget:nop\nmov ax,[bx+{expr}]\n'
                        self.assertEqual(assemble(source, optimize=level, compatibility='nasm3'),
                                         bytes.fromhex('90 8b 87 00 00'))

    def test_scalars_and_register_coefficients_still_cancel(self):
        source = ('cpu 8088\norg 256\ntarget:nop\n'
                  'mov ax,[bx+target*0]\n'
                  'mov ax,[(bx+target)*2-bx-target]\n'
                  'dw target*3-target*2\n')
        self.assertEqual(assemble(source, compatibility='nasm3', optimize=9),
                         bytes.fromhex('90 8b 07 8b 87 00 01 00 01'))

    def test_impossible_multiplications_are_rejected(self):
        for cpu in ('8086', '8088'):
            for expression in ('target*2', 'target*-2', 'target*target'):
                for consumer in ('mov ax,{}', 'mov ax,[bx+{}]', 'dw {}', 'value equ {}'):
                    with self.subTest(cpu=cpu, expr=expression, consumer=consumer):
                        source = f'cpu {cpu}\ntarget:nop\n' + consumer.format(expression) + '\n'
                        with self.assertRaises(AssemblyError):
                            assemble(source, compatibility='nasm3')
            with self.subTest(cpu=cpu, expr='bx*target'):
                with self.assertRaises(AssemblyError):
                    assemble(f'cpu {cpu}\ntarget:nop\nmov ax,[bx*target]\n',
                             compatibility='nasm3')

    def test_expression_and_address_metadata_agree(self):
        def lookup(name):
            return Value(4, symbolic=True, section='.text', relocation=1)
        for expr in EQUIVALENTS:
            with self.subTest(expr=expr):
                self.assertEqual(evaluate(expr, lookup).relocation, 1)
                value, registers = evaluate_address('bx+' + expr, lookup)
                self.assertEqual(value.relocation, 1)
                self.assertEqual(registers, {'bx': 1})


if __name__ == '__main__':
    unittest.main()
