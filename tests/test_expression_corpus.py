"""Expression semantics pinned to NASM 3.02 flat-binary output."""

import unittest
from pathlib import Path

from pynasm import assemble


FIXTURES = Path(__file__).parent / "fixtures" / "generated"


class ExpressionCorpusTests(unittest.TestCase):
    def test_precedence_ternary_shifts_and_comparisons(self):
        source = (FIXTURES / "expressions.asm").read_text(encoding="ascii")
        expected = (FIXTURES / "expressions.bin").read_bytes()
        self.assertEqual(assemble(source, compatibility="nasm3"), expected)


if __name__ == "__main__":
    unittest.main()
