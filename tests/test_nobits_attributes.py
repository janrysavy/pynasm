"""NASM flat-binary NOBITS placement cannot mix real and virtual attributes."""
import itertools
import unittest

from pynasm import Assembler, AssemblyError, assemble

REAL = ("align=16", "start=512", "follows=.data")
VIRTUAL = ("vstart=512", "vfollows=.data", "valign=16")
HEADER = "cpu {cpu}\nbits 16\nsection .data\ndb 1\n"
TRAILER = "field: resb 1\nsection .text\ndw field\n"


def mixed_sources():
    for real, virtual in itertools.product(REAL, VIRTUAL):
        yield f"section .bss {real} {virtual}\n" + TRAILER
        yield f"section .bss {virtual} {real}\n" + TRAILER
        yield f"section .bss {real}\nresb 0\nsection .bss {virtual}\n" + TRAILER
    for alignment in (1, 4, 16):
        for directive in (f"sectalign {alignment}", f"alignb {alignment}"):
            yield "section .bss vstart=512\n" + directive + "\n" + TRAILER


class NobitsAttributeTests(unittest.TestCase):
    def test_mixed_real_virtual_attributes_are_rejected(self):
        # These are explicit NASM 3.02 diagnostic rejections, not legal cases
        # accidentally counted as passing when both implementations fail.
        for body in mixed_sources():
            for cpu, level in itertools.product(("8086", "8088"), (0, 1, 9)):
                with self.subTest(body=body, cpu=cpu, level=level):
                    with self.assertRaisesRegex(AssemblyError, "mix real and virtual"):
                        assemble(HEADER.format(cpu=cpu) + body,
                                 compatibility="nasm3", optimize=level)

    def test_default_alignment_and_unmixed_controls_stay_valid(self):
        controls = (("section .bss vstart=512\n", "0002000001"),
                    ("section .bss vfollows=.data\n", "0800000001"),
                    ("section .bss align=16\n", "1000000001"),
                    ("section .bss start=512\n", "0002000001"),
                    ("section .bss follows=.data\n", "0800000001"),
                    ("section .bss vstart=512\nsectalign off\nalignb 16\n", "0002000001"))
        for body, expected in controls:
            for cpu, level in itertools.product(("8086", "8088"), (0, 1, 9)):
                with self.subTest(body=body, cpu=cpu, level=level):
                    self.assertEqual(assemble(HEADER.format(cpu=cpu) + body + TRAILER,
                                              compatibility="nasm3", optimize=level),
                                     bytes.fromhex(expected))
        source = "cpu 8086\nsection .data align=16 vstart=512\nfield: db 1\nsection .text\ndw field\n"
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("0002") + bytes(14) + b"\x01")

    def test_attribute_tracking_resets_after_failure_and_on_reuse(self):
        asm = Assembler(compatibility="nasm3")
        bad = HEADER.format(cpu="8088") + "section .bss align=16 vstart=512\n" + TRAILER
        with self.assertRaisesRegex(AssemblyError, "mix real and virtual"):
            asm.assemble(bad, filename="invalid.asm")
        self.assertEqual(asm.listing, ())
        for body, expected in (("section .bss vstart=512\n", "0002000001"),
                               ("section .bss align=16\n", "1000000001")):
            self.assertEqual(asm.assemble(HEADER.format(cpu="8088") + body + TRAILER),
                             bytes.fromhex(expected))


if __name__ == "__main__":
    unittest.main()
