"""NASM backquoted bytes used by 8086/8088 data and immediate operands."""
import unittest

from pynasm import assemble
from pynasm.expression import string_bytes


# Exact NASM 3.02 output, checked using cpu 8086 (the shared 8086/8088 ISA).
CASES = (
    (r"\e", "1b"), (r"\u00e9", "c3a9"), (r"\u1234", "e188b4"),
    (r"\U0001f600", "f09f9880"), (r"\x1", "01"), (r"\400", "00"),
    (r"\777", "ff"), (r"a\qa", "617161"), (r"\?", "3f"),
    (r"\a\b\t\n\v\f\r", "0708090a0b0c0d"),
    (r"\x\xG\x123", "7878471233"), (r"\u12\u\uZ123", "1275755a313233"),
    (r"\078\7777", "0738ff37"), (r"\d255\o377\Xff", "ffffff"),
    (r"\x{1234}\d{256}\o{777}", "3400ff"),
    (r"\u{1f600}\U{100000041}", "f09f988041"),
    (r"\x{}\u{}", "0000"), (r"\x{q}\u{123q}", "787b717d757b313233717d"),
    (r"\^A\^a\^?\^@", "01017f00"),
    (r"\uD800", "eda080"), (r"\U00110000", "f4908080"),
    (r"\U04000000", "fc8480808080"),
    (r"\U7fffffff\U80000000\Uffffffff", "fdbfbfbfbfbffe8080808080ffbfbfbfbfbf"),
    (r"\`\'\"\\", "6027225c"),
)


class StringEscapeTests(unittest.TestCase):
    def test_backquoted_data_bytes(self):
        for cpu in ("8086", "8088"):
            for escaped, expected in CASES:
                with self.subTest(cpu=cpu, escaped=escaped):
                    source = f"cpu {cpu}\ndb `{escaped}`\n"
                    self.assertEqual(assemble(source, compatibility="nasm3"),
                                     bytes.fromhex(expected))

    def test_backquoted_8086_immediates(self):
        for cpu in ("8086", "8088"):
            with self.subTest(cpu=cpu):
                source = f"cpu {cpu}\n" + r"mov ax,`\e`" + "\n" + r"mov bx,`\u00e9`" + "\n"
                self.assertEqual(assemble(source, compatibility="nasm3"),
                                 bytes.fromhex("b8 1b 00 bb c3 a9"))

    def test_plain_quotes_remain_verbatim(self):
        for quote in ("'", '"'):
            self.assertEqual(string_bytes(quote + r"\e\u1234" + quote), br"\e\u1234")
        self.assertEqual(string_bytes("`\xe9`"), b"\xe9")

    def test_preprocessor_lengths_and_substrings_use_decoded_bytes(self):
        source = "cpu 8088\n" + r"""
%strlen length `\u00e9\e`
%substr tail `\u00e9\e`,2,2
db length,tail
"""
        self.assertEqual(assemble(source, compatibility="nasm3"), bytes.fromhex("03 a9 1b"))


if __name__ == "__main__":
    unittest.main()
