"""NASM backquoted bytes used by 8086/8088 data and immediate operands."""
import unittest

from pynasm import assemble


class StringEscapeTests(unittest.TestCase):
    def test_backquoted_data_bytes(self):
        # Exact NASM 3.02 output; these expectations need no native binary.
        cases = ((r"\e", "1b"), (r"\u00e9", "c3a9"),
                 (r"\u1234", "e188b4"), (r"\U0001f600", "f09f9880"),
                 (r"\x1", "01"), (r"\400", "00"),
                 (r"\777", "ff"), (r"a\qa", "617161"), (r"\?", "3f"))
        for cpu in ("8086", "8088"):
            for escaped, expected in cases:
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


if __name__ == "__main__":
    unittest.main()
