"""A late alignment requirement must relocate every earlier symbol consistently."""
import itertools
import unittest

from pynasm import Assembler, AssemblyError


class SectionAlignmentTests(unittest.TestCase):
    def test_late_alignment_relocates_preceding_labels(self):
        for kind, directive in ((".bss", "alignb 32"), (".data", "align 32,db 0"),
                                (".data", "sectalign 32")):
            for cpu, profile, level, origin in itertools.product(
                    ("8086", "8088"), ("nasm09839", "nasm3"), (0, 1, 9), (0, 1, 256, 31744)):
                with self.subTest(kind=kind, directive=directive, cpu=cpu,
                                  profile=profile, level=level, origin=origin):
                    data = "resb 1" if kind == ".bss" else "db 0xa5"
                    source = (f"cpu {cpu}\nbits 16\norg {origin}\nmov ax,item\n"
                              f"section {kind} align=16\nitem: {data}\n{directive}\n")
                    address = (origin + 3 + 31) & ~31
                    expected = b"\xb8" + address.to_bytes(2, "little")
                    if kind != ".bss":
                        expected += bytes(address-origin-3) + b"\xa5"
                        if directive.startswith("align "):
                            expected += bytes(31)
                    asm = Assembler(compatibility=profile, optimize=level)
                    self.assertEqual(asm.assemble(source), expected)
                    self.assertEqual(asm.symbols["item"], address)
                    record = next(r for r in asm.listing if r.text.startswith("item:"))
                    self.assertEqual(record.address, address)
                    self.assertEqual(record.offset, 0)

    def test_repeated_alignment_does_not_lower_a_requirement(self):
        for cpu, profile, level in itertools.product(
                ("8086", "8088"), ("nasm09839", "nasm3"), (0, 1, 9)):
            with self.subTest(cpu=cpu, profile=profile, level=level):
                source = (f"cpu {cpu}\nmov ax,item\nsection .data align=16\nitem: db 1\n"
                          "section .data align=32\nsection .data align=1\ndb 2\n")
                asm = Assembler(compatibility=profile, optimize=level)
                self.assertEqual(asm.assemble(source), b"\xb8\x20\x00" + bytes(29) + b"\x01\x02")
                self.assertEqual(asm.symbols["item"], 32)

    def test_default_can_be_lowered_and_reuse_forgets_prior_alignment(self):
        asm = Assembler(compatibility="nasm3")
        for alignment, address in ((32, 32), (1, 3), (16, 16), (1, 3)):
            source = ("cpu 8088\nmov ax,item\n"
                      f"section .data align={alignment}\nitem: db 0xa5\n")
            self.assertEqual(asm.assemble(source), b"\xb8" + address.to_bytes(2, "little") +
                             bytes(address-3) + b"\xa5")

    def test_alignment_can_decrease_across_relaxation_passes(self):
        source = ("cpu 8086\nbits 16\njmp after\nafter:\n"
                  "section .data align=1<<($-$$)\nitem: db 0xa5\nsection .text\ndw item\n")
        for level, expected in ((0, "e900000800000000a5"),
                                (1, "e900000800000000a5"), (9, "eb000400a5")):
            for cpu in ("8086", "8088"):
                with self.subTest(level=level, cpu=cpu):
                    self.assertEqual(Assembler(compatibility="nasm3", optimize=level).assemble(
                        source.replace("cpu 8086", "cpu " + cpu)), bytes.fromhex(expected))

    def test_invalid_smaller_alignment_is_not_silently_ignored(self):
        for value in (0, 3, -1):
            for profile in ("nasm09839", "nasm3"):
                with self.subTest(value=value, profile=profile), self.assertRaises(AssemblyError):
                    Assembler(compatibility=profile).assemble(
                        f"cpu 8086\nsection .data align=32\nsection .data align={value}\ndb 1\n")


if __name__ == "__main__":
    unittest.main()
