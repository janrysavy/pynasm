"""8086/8088 branch relaxation must account for intervening alignment."""
import unittest

from pynasm import assemble


class JumpAlignmentTests(unittest.TestCase):
    def test_alignment_absorbs_the_entire_shortening(self):
        # A near JMP puts target at 130. Changing it to a short JMP adds
        # one byte of ALIGN padding, so target stays at 130, outside rel8.
        expected = bytes.fromhex("e9 7f 00") + bytes(127) + b"\x90"
        for cpu in ("8086", "8088"):
            for profile in ("nasm09839", "nasm3"):
                with self.subTest(cpu=cpu, profile=profile):
                    source = (f"cpu {cpu}\nbits 16\njmp target\n"
                              "align 128, db 0\ndb 0, 0\ntarget: nop\n")
                    self.assertEqual(assemble(source, optimize=9,
                                              compatibility=profile), expected)


if __name__ == "__main__":
    unittest.main()
