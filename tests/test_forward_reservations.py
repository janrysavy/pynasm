"""Forward EQU metadata must not prematurely reject valid reservations."""
import unittest
from pynasm import Assembler, AssemblyError, assemble


class ForwardReservationTests(unittest.TestCase):
    def test_direct_and_aliased_forward_lengths(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for declaration, count in (('', 'end-start'),
                                           ('length equ end-start\n', 'length'),
                                           ('length equ other\nother equ end-start\n', 'length')):
                    with self.subTest(cpu=cpu, level=level, count=count, declaration=declaration):
                        source = f'cpu {cpu}\n{declaration}resb {count}\nstart:db 1,2\nend:\n'
                        self.assertEqual(assemble(source, compatibility='nasm3', optimize=level),
                                         bytes.fromhex('00 00 01 02'))

    def test_unresolved_and_self_growing_counts_remain_errors(self):
        for source in ('resb missing\n', 'resb target\ntarget:nop\n'):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility='nasm3')

    def test_cycle_and_reuse_match_reference(self):
        asm = Assembler(compatibility='nasm3')
        self.assertEqual(asm.assemble('a equ a\nresb a\n'), b'')
        with self.assertRaises(AssemblyError):
            asm.assemble('resb missing\n')
        self.assertEqual(asm.assemble('resb end-start\nstart:db 1,2\nend:\n'),
                         bytes.fromhex('00 00 01 02'))


if __name__ == '__main__':
    unittest.main()
