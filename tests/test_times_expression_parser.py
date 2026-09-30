"""Expression-aware TIMES prefix boundaries; NASM 3.02 source 4a56d66ed962."""
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from pynasm.expression import Value, evaluate, evaluate_prefix
from nasm_reference import reference, verify_version

ACCEPTED = [
    ('a equ 2\nb equ 3\ntimes (a + b) nop\n', '90'*5),
    ('a equ 2\nb equ 3\ntimes a + b nop\n', '90'*5),
    ('a equ 2\nb equ 3\ntimes ((a * b) - 1) nop\n', '90'*5),
    ('a equ 2\nb equ 3\ntimes (a == 2 ? b : 0) nop\n', '90'*3),
    ('a equ 2\nb equ 3\ntimes(a + b)nop\n', '90'*5),
    ("times (')' - ')' + 1) nop\n", '90'),
    ('times __?ilog2f?__(8) nop\n', '90'*3),
    ('times 2 times 3 nop\n', '90'*3),
    ('times 0 times 1 nop\n', '90'),
    ('times -1 times 2 nop\n', '9090'),
    ('rep times 2 movsb\n', 'f3a4'*2),
    ('times 2 rep times 3 movsb\n', 'f3a4'*3),
    ('times 2 cs rep movsb\n', '2ef3a4'*2),
    ('o16 times 2 nop\n', '9090'),
    ('a16 times 2 nop\n', '9090'),
    ('times 2 rep\n', 'f3f3'),
    ('times 2\nnop\n', '90'),
    ('times 0 times 2\nnop\n', '90'),
    ('times (finish - start) nop\nstart: db 0\nfinish: db 1\n', '900001'),
    ('org 0x100\na: db 1\nb: times (b - a) dw 0x1234\n', '013412'),
    ('%macro m 2\ntimes (%1 + %2) nop\n%endmacro\nm 2,3\n', '90'*5),
    ('label: times 1 times 2 nop\ndw label\n', '90900000'),
]
REJECTED = [
    'times (2 + missing) nop\n', 'times (2 + 1 nop\n', 'times (2 / 0) nop\n',
    'times 2 times -1 nop\n', 'times -1\n', 'times missing\n', 'times\n',
    'a: times a times 1 nop\n', 'times $ nop\n',
    'a equ 2\nb equ 3\ntimes (a + b)) nop\n',
]


class TimesExpressionParserTests(unittest.TestCase):
    def test_valid_expression_and_prefix_boundaries(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source, expected in ACCEPTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        actual = Assembler(compatibility='nasm3', optimize=level).assemble(
                            f'cpu {cpu}\n' + source)
                        self.assertEqual(actual.hex(), expected)

    def test_invalid_counts_and_bodies(self):
        for cpu in ('8086', '8088'):
            for level in (0, 1, 9):
                for source in REJECTED:
                    with self.subTest(cpu=cpu, level=level, source=source):
                        with self.assertRaises(AssemblyError):
                            Assembler(compatibility='nasm3', optimize=level).assemble(
                                f'cpu {cpu}\n' + source)

    def test_expression_prefix_reports_consumed_source(self):
        source = "  (first + 2)   db 'x'"
        lookup = lambda name: Value(3) if name == 'first' else Value(0, unresolved=True)
        value, end = evaluate_prefix(source, lookup)
        self.assertEqual(value.number, 5)
        self.assertEqual(source[end:], "   db 'x'")
        self.assertEqual(evaluate(source[:end], lookup), value)

    def test_bare_times_does_not_iterate_count(self):
        # Native large counts are excluded from live batches: NASM loops over
        # each zero-byte instruction. This tests our allocation-free no-op path.
        self.assertEqual(Assembler(compatibility="nasm3").assemble(
            "times 0x7fffffff\nnop\n"), b"\x90")

    def test_legacy_simple_times_is_unchanged(self):
        self.assertEqual(Assembler(compatibility='nasm09839').assemble('times 2 nop\n'), b'\x90\x90')

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
