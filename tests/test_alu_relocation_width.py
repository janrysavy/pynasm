"""NASM3 must not automatically sign-shorten a relocatable ALU immediate."""
import unittest
from pynasm import assemble

ALU = (('add', 0x05, 0), ('or', 0x0d, 1), ('adc', 0x15, 2),
       ('sbb', 0x1d, 3), ('and', 0x25, 4), ('sub', 0x2d, 5),
       ('xor', 0x35, 6), ('cmp', 0x3d, 7))


class AluRelocationWidthTests(unittest.TestCase):
    def test_label_immediates_keep_word_width(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for mnemonic, accumulator, group in ALU:
                    for operand, opcode in (
                            ('ax', bytes((accumulator,))),
                            ('bx', bytes((0x81, 0xc3 | group << 3))),
                            ('word [bx]', bytes((0x81, 0x07 | group << 3)))):
                        for expression, value in (('target', 0), ('target+127', 127),
                                                  ('target-128', -128)):
                            with self.subTest(cpu=cpu, level=level, mnemonic=mnemonic,
                                              operand=operand, expression=expression):
                                source = f'cpu {cpu}\ntarget:nop\n{mnemonic} {operand},{expression}\n'
                                expected = b'\x90' + opcode + (value & 0xffff).to_bytes(2,'little')
                                self.assertEqual(assemble(source, optimize=level, compatibility='nasm3'),
                                                 expected)

    def test_explicit_byte_and_scalar_difference_can_shorten(self):
        for cpu in ('8086', '8088'):
            for mnemonic, _, group in ALU:
                for expression in ('byte target', 'target-target'):
                    with self.subTest(cpu=cpu, mnemonic=mnemonic, expression=expression):
                        source = f'cpu {cpu}\ntarget:nop\n{mnemonic} ax,{expression}\n'
                        self.assertEqual(assemble(source, optimize=9, compatibility='nasm3'),
                                         bytes((0x90, 0x83, 0xc0 | group << 3, 0)))

    def test_forward_label_layout_uses_unshortened_immediate(self):
        # Pinned NASM 3.02 -O0/-O1/-O9 bytes: all three words see target == 11.
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                with self.subTest(cpu=cpu, level=level):
                    source = f'cpu {cpu}\nadd ax,target\nadd bx,target\nadd word [bx],target\ntarget:nop\n'
                    self.assertEqual(assemble(source, optimize=level, compatibility='nasm3'),
                                     bytes.fromhex('05 0b 00 81 c3 0b 00 81 07 0b 00 90'))


if __name__ == '__main__':
    unittest.main()
