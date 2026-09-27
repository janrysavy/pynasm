"""Pinned exhaustive 8086 encoding corpus from pts/mininasm."""

import unittest
from pathlib import Path

from pynasm import Assembler, assemble


FIXTURES = Path(__file__).parent / "fixtures" / "mininasm"


class MininasmCorpusTests(unittest.TestCase):
    def test_input0_and_input1_foundations(self):
        for name in ("input0", "input1"):
            with self.subTest(source=name):
                source = (FIXTURES / f"{name}.asm").read_text(encoding="latin-1")
                golden = (FIXTURES / f"{name.upper()}.IMG").read_bytes()
                self.assertEqual(assemble(source, optimize=1), golden)

    def test_input2_exhaustive_8086_encoding(self):
        source = (FIXTURES / "input2.asm").read_text(encoding="latin-1")
        golden = (FIXTURES / "INPUT2.IMG").read_bytes()
        # The upstream golden was produced with a COM origin. The source itself
        # has no ORG, so make that reference condition explicit in the test.
        actual = assemble("org 0x100\n" + source, optimize=1)
        self.assertEqual(len(actual), 37244)
        self.assertEqual(actual, golden)

    def test_syntax_integration(self):
        source = (FIXTURES / "syntax.nasm").read_text(encoding="latin-1")
        golden = (FIXTURES / "syntax.O9.bin").read_bytes()
        actual = Assembler(optimize=9, include_paths=[FIXTURES],
                           defines={"CMDVAL": "15"}).assemble(
                               source, filename=str(FIXTURES / "syntax.nasm"))
        self.assertEqual(actual, golden)

    def test_upstream_nested_include_program(self):
        fixture_root = FIXTURES / "include"
        source_path = fixture_root / "test" / "INCLUDE.ASM"
        golden = (fixture_root / "test" / "INCLUDE.COM").read_bytes()
        actual = Assembler(optimize=9, include_paths=[fixture_root]).assemble(
            source_path.read_text(encoding="latin-1"), filename=str(source_path))
        self.assertEqual(actual, golden)

    def test_upstream_xtest_binaries(self):
        fixtures = FIXTURES / "xtest"
        for source_path in sorted(fixtures.glob("*.nasm")):
            for level in (0, 1, 9):
                with self.subTest(source=source_path.name, optimization=level):
                    golden = (fixtures / (source_path.stem + f".O{level}.bin")).read_bytes()
                    # INPUT2.IMG retains NASM 0.98.39's XCHG orientation;
                    # current upstream reg/xchg goldens use the newer one.
                    # reg.O1.bin is pinned directly from NASM 3.02 because
                    # current mininasm mixes the two versions' O1 choices.
                    profile = "nasm3" if source_path.stem in ("reg", "xchg") else "nasm09839"
                    actual = Assembler(optimize=level, compatibility=profile,
                                       include_paths=[FIXTURES],
                                       defines={"CMDVAL": "15"}).assemble(
                                           source_path.read_text(encoding="latin-1"),
                                           filename=str(source_path))
                    self.assertEqual(actual, golden)

    def test_upstream_boot_programs(self):
        fixtures = FIXTURES / "programs"
        levels = {"basic": 9, "bricks": 1, "doom": 9, "fbird": 1,
                  "invaders": 9, "os": 1, "pillman": 9, "rogue": 1}
        for name, level in levels.items():
            with self.subTest(program=name):
                source_path = fixtures / f"{name}.asm"
                golden = (fixtures / f"{name}.O{level}.bin").read_bytes()
                actual = Assembler(optimize=level, include_paths=[fixtures]).assemble(
                    source_path.read_text(encoding="latin-1"), filename=str(source_path))
                self.assertEqual(actual, golden)


if __name__ == "__main__":
    unittest.main()
