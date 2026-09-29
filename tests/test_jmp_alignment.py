"""8086/8088 relaxation must use resolved ALIGN directives, not source text."""
import unittest

from pynasm import Assembler, AssemblyError, assemble


# Prefix, zero fill length, and trailing NOP are pinned NASM 3.02 -O9 bytes.
CASES = (
    ("jmp target\nalign 128, db 0\ndb 0,0\ntarget: nop", "e9 7f 00", 127),
    ("jz target\npad: align 128, db 0\ndb 0,0\ntarget: nop", "75 03 e9 7d 00", 125),
    ("jmp target\npad: align (1 << 7), db 0\ndb 0,0\ntarget: nop", "e9 7f 00", 127),
    ("N equ 128\njmp target\npad align N, db 0\ndb 0,0\ntarget: nop", "e9 7f 00", 127),
    ("jmp target\ntimes 126 db 0\npad: align 2, db 0\ndb 0\ntarget: nop", "eb 7f", 127),
    ("jz target\ntimes 126 db 0\npad: align 2, db 0\ndb 0\ntarget: nop", "74 7f", 127),
    ("es jmp target\nalign 128, db 0\ndb 0,0,0\ntarget: nop", "26 e9 7f 00", 127),
    ("entry: jmp .target\n.pad: align 128, db 0\ndb 0,0\n.target: nop", "e9 7f 00", 127),
)


class JumpAlignmentTests(unittest.TestCase):
    def test_alignment_relaxation(self):
        for cpu in ("8086", "8088"):
            for profile in ("nasm09839", "nasm3"):
                for body, prefix, zeros in CASES:
                    with self.subTest(cpu=cpu, profile=profile, source=body):
                        expected = bytes.fromhex(prefix) + bytes(zeros) + b"\x90"
                        actual = assemble(f"cpu {cpu}\nbits 16\n{body}\n",
                                          optimize=9, compatibility=profile)
                        self.assertEqual(actual, expected)

    def test_explicit_short_is_not_silently_widened(self):
        for cpu in ("8086", "8088"):
            for profile in ("nasm09839", "nasm3"):
                with self.subTest(cpu=cpu, profile=profile):
                    source = (f"cpu {cpu}\njmp short target\n"
                              "align 128, db 0\ndb 0,0\ntarget: nop\n")
                    with self.assertRaisesRegex(AssemblyError, "out of range"):
                        assemble(source, optimize=9, compatibility=profile)

    def test_reuse_and_listing_use_final_layout(self):
        asm = Assembler(optimize=9, compatibility="nasm3")
        for body, prefix, zeros in CASES:
            expected = bytes.fromhex(prefix) + bytes(zeros) + b"\x90"
            self.assertEqual(asm.assemble("cpu 8088\n" + body + "\n"), expected)
            self.assertEqual(b"".join(row.data for row in asm.listing), expected)
        self.assertEqual(asm.assemble("cpu 8088\njmp next\nnext: nop"), b"\xeb\x00\x90")


if __name__ == "__main__":
    unittest.main()
