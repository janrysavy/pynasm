"""NASM preprocessor percent tokens are not unspaced arithmetic operators."""
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version

BAD_EXPRESSIONS = ('5%2', '5 %2', '5%%2', '5 %%2', '5%+2', '5%-2',
                   '5%%foo', '5 %%foo', '5%%~2', '5%0x2', '5%%0x2')
CONTEXTS = ('db {e}\n', 'mov ax,{e}\n', 'mov ax,[bx+({e})]\n',
            '%assign value {e}\ndb value\n', '%if {e}\ndb 1\n%endif\n')
REJECTED = ['foo equ 2\n' + context.format(e=expression)
            for expression in BAD_EXPRESSIONS for context in CONTEXTS]
REJECTED += ['%define unused %1\ndb 1\n', '%define unused %%foo\ndb 1\n',
             '%define unused 5%2\ndb 1\n', '%if 1\ndb 3\n%elif 5%2\ndb 1\n%endif\n']
ACCEPTED = [
    ('db ' + e + '\n', bytes([n])) for e, n in (
        ('5% 2', 1), ('5 % 2', 1), ('5%% 2', 1), ('5 %% 2', 1),
        ('5%%+2', 1), ('5%%-2', 1), ('5%~2', 5), ('5%(2)', 1),
        ('5%%(2)', 1), ("5%'a'", 5), ("5%%'a'", 5))
]
ACCEPTED += [
    ('%if 0\n%elif 5%2\ndb 1\n%endif\n', b'\x01'),
    ('%if 0\n%elif 5%%2\ndb 1\n%endif\n', b'\x01'),
    ('foo equ 2\ndb 5%foo,5% foo,5%% foo\n', b'\x01\x01\x01'),
    ('db "5%2",\'%+1\',`%%local`\n', b'5%2%+1%%local'),
    ('db 1 ; %1 %%foo\n', b'\x01'),
    ('%if 0\ndb 5%2\n%define unused %1\n%endif\ndb 1\n', b'\x01'),
    ('%macro unused 0\ndb %1\n%endmacro\ndb 1\n', b'\x01'),
    ('%macro m 1\ndb %1 % 2\n%endmacro\nm 5\n', b'\x01'),
    ('%macro m 0\n%%foo:db 5\ndb 7 %% (%%foo-$$+2)\n%endmacro\nm\n', b'\x05\x01'),
    ('%assign n 5%%+2\n%if n\ndb n\n%endif\n', b'\x01'),
]


class PercentTokenBoundaryTests(unittest.TestCase):
    def test_invalid_unexpanded_macro_tokens(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source in REJECTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        with self.assertRaises(AssemblyError):
                            Assembler(compatibility='nasm3', optimize=level).assemble(
                                f'cpu {cpu}\n' + source)

    def test_arithmetic_strings_and_macro_controls(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source, expected in ACCEPTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        self.assertEqual(Assembler(compatibility='nasm3', optimize=level).assemble(
                            f'cpu {cpu}\n' + source), expected)

    def test_historical_profile_is_unchanged(self):
        self.assertEqual(Assembler(compatibility='nasm09839').assemble('db 5%2\n'), b'\x01')

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_pinned_reference(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for source, expected in [(s, None) for s in REJECTED] + ACCEPTED:
            for level in (0, 1, 9):
                with self.subTest(source=source, level=level):
                    self.assertEqual(reference(native, 'cpu 8086\n' + source, level), expected)


if __name__ == '__main__':
    unittest.main()
