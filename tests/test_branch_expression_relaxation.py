"""Regressions for label-plus-addend relaxation (NASM 3.02 -O9 goldens)."""
import unittest

from pynasm import assemble


class BranchExpressionRelaxationTests(unittest.TestCase):
    def test_forward_label_addend_uses_short_form(self):
        # A short JMP plus the same padding can reach target+1 with rel8=127.
        expected = b"\xeb\x7f" + bytes(126) + b"\x90\x90"
        for cpu in ("8086", "8088"):
            for alignment in ("align 2, db 0", "pad: align 2, db 0"):
                with self.subTest(cpu=cpu, alignment=alignment):
                    source = (f"cpu {cpu}\nbits 16\njmp target+1\n"
                              f"times 126 db 0\n{alignment}\ntarget:nop\nnop\n")
                    self.assertEqual(assemble(source, optimize=9,
                                              compatibility="nasm3"), expected)

    def test_explicit_short_proves_the_target_is_encodable(self):
        expected = b"\xeb\x7f" + bytes(126) + b"\x90\x90"
        for cpu in ("8086", "8088"):
            for alignment in ("align 2, db 0", "pad: align 2, db 0"):
                with self.subTest(cpu=cpu, alignment=alignment):
                    source = (f"cpu {cpu}\nbits 16\njmp short target+1\n"
                              f"times 126 db 0\n{alignment}\ntarget:nop\nnop\n")
                    self.assertEqual(assemble(source, optimize=9,
                                              compatibility="nasm3"), expected)

    def test_numerically_forward_target_based_on_earlier_label_must_not_move(self):
        # Removing the exact-symbol guard is unsafe: this target's anchor is
        # before the branch, so its value cannot shift when the JMP shrinks.
        expected = b"\x90\xe9\x7f\x00" + bytes(127) + b"\x90"
        for cpu in ("8086", "8088"):
            with self.subTest(cpu=cpu):
                source = (f"cpu {cpu}\nbits 16\nanchor:nop\njmp anchor+131\n"
                          "times 127 db 0\nnop\n")
                self.assertEqual(assemble(source, optimize=9,
                                          compatibility="nasm3"), expected)


if __name__ == "__main__":
    unittest.main()
