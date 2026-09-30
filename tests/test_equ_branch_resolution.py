"""Forward EQU values remain unresolved until their dependencies are known."""
import unittest
from pynasm import Assembler, AssemblyError, assemble


class EquBranchResolutionTests(unittest.TestCase):
    def test_early_equ_preserves_native_boundary_choice(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for definition in ('alias equ target', 'alias: equ target',
                                   'alias equ other\nother equ target'):
                    for mnemonic, opcode in (('jz', 0x75), ('jnz', 0x74), ('jc', 0x73)):
                        with self.subTest(cpu=cpu, level=level, definition=definition,
                                          mnemonic=mnemonic):
                            source = (f'cpu {cpu}\n{definition}\n{mnemonic} alias\n'
                                      'times 126 db 0\ntarget:nop\n')
                            expected = bytes((opcode, 3, 0xe9, 126, 0)) + bytes(126) + b'\x90'
                            self.assertEqual(assemble(source, optimize=level, compatibility='nasm3'),
                                             expected)

    def test_short_alias_and_direct_forward_label_still_shorten(self):
        cases = (
            ('alias equ target\njz alias\nnop\ntarget:nop', '74 01 90 90'),
            ('alias equ target\njz short alias\ntimes 126 db 0\ntarget:nop',
             '74 7e' + '00'*126 + '90'),
            ('alias equ target\njz target\ntimes 126 db 0\ntarget:nop',
             '74 7e' + '00'*126 + '90'),
        )
        for cpu in ('8086', '8088'):
            for source, expected in cases:
                with self.subTest(cpu=cpu, source=source):
                    self.assertEqual(assemble(f'cpu {cpu}\n'+source+'\n',
                                              optimize=9, compatibility='nasm3'),
                                     bytes.fromhex(expected))

    def test_circular_equ_keeps_native_compatibility(self):
        for body in ('a equ b\nb equ a\ndw a', 'a equ a\ndw a'):
            with self.subTest(source=body):
                # NASM 3.02 accepts these cycles with an initial zero value.
                self.assertEqual(assemble('cpu 8088\n'+body+'\n',
                                          compatibility='nasm3'), b'\x00\x00')

    def test_failed_and_successful_reuse(self):
        asm = Assembler(optimize=9, compatibility='nasm3')
        for _ in range(2):
            with self.assertRaises(AssemblyError):
                asm.assemble('cpu 8088\na equ absent\njz a\n')
            self.assertEqual(asm.listing, ())
            source='cpu 8088\na equ target\njz a\ntimes 126 db 0\ntarget:nop\n'
            expected=bytes.fromhex('75 03 e9 7e 00')+bytes(126)+b'\x90'
            self.assertEqual(asm.assemble(source), expected)
            self.assertEqual(b''.join(row.data for row in asm.listing),expected)
            self.assertEqual(asm.assemble('cpu 8088\njz target\ntarget:nop\n'), b'\x74\x00\x90')


if __name__ == '__main__':
    unittest.main()
