"""All NASM 3.02 8086/FPU template rows against a pinned binary golden."""

import unittest
from pathlib import Path

from pynasm import Assembler, AssemblyError
from pynasm.fpu8087 import FPU_FIXED, FPU_MEMORY, FPU_REGISTER


FIXTURES = Path(__file__).parent / "fixtures" / "generated"


class FpuCorpusTests(unittest.TestCase):
    def test_every_8087_template(self):
        rows = (len(FPU_FIXED) + sum(map(len, FPU_MEMORY.values())) +
                sum(map(len, FPU_REGISTER.values())))
        self.assertEqual(rows, 162)
        source = (FIXTURES / "fpu8087.asm").read_text(encoding="ascii")
        self.assertEqual(len(source.splitlines()) - 1, 162)
        actual = Assembler(optimize=0, compatibility="nasm3").assemble(source)
        self.assertEqual(actual, (FIXTURES / "fpu8087.bin").read_bytes())

    def test_invalid_8087_operands(self):
        for instruction in ("fadd st8", "fadd st(3)",
                            "fadd st1,st2", "fild byte [bx]", "faddp st0,st1"):
            with self.subTest(instruction=instruction), self.assertRaises(AssemblyError):
                Assembler(compatibility="nasm3").assemble("cpu 8086\n" + instruction)

    def test_unsized_fpu_memory_defaults_to_32_bits(self):
        source = "cpu 8086\nfadd [bx]\nfmul [bx]\nfiadd [bx]\nfild [bx]\nfstp [bx]"
        self.assertEqual(Assembler(compatibility="nasm3").assemble(source),
                         bytes.fromhex("d8 07 d8 0f da 07 db 07 d9 1f"))


if __name__ == "__main__":
    unittest.main()
