"""Pinned NASM 3.02 goldens for representative non-FPU 8086 templates."""

import unittest
from pathlib import Path

from pynasm import Assembler


FIXTURES = Path(__file__).parent / "fixtures" / "generated"


class InsnsCorpusTests(unittest.TestCase):
    def test_expanded_8086_non_fpu_templates(self):
        source = (FIXTURES / "insns8086.asm").read_text(encoding="ascii")
        self.assertEqual(source.count("; row "), 354)
        for level in (0, 9):
            with self.subTest(optimize=level):
                actual = Assembler(optimize=level, compatibility="nasm3").assemble(source)
                expected = (FIXTURES / f"insns8086.O{level}.bin").read_bytes()
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
