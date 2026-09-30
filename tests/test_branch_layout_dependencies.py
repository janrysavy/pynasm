"""Source-position provenance for 8086/8088 branch target expressions."""
import unittest

from pynasm import Assembler, AssemblyError, assemble
from pynasm.expression import Value, evaluate


# Exact NASM 3.02 -O9 output; test both accepted CPU spellings.
SHORT = b"\xeb\x7f" + bytes(126) + b"\x90\x90"
CASES = (
    ("jmp 1+target\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\nnop", SHORT),
    ("jmp target-(-1)\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\nnop", SHORT),
    ("jmp target+(tail-tail)+1\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\ntail:nop", SHORT),
    ("jmp target+(after-before)\ntimes 126 db 0\nbefore:align 2,db 0\ntarget:nop\nafter:nop", SHORT),
    ("jmp alias\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\nnop\nalias equ target+1", SHORT),
    ("jz alias\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\nnop\nalias equ target+1",
     b"\x74\x7f" + bytes(126) + b"\x90\x90"),
    ("entry:jmp .target+1\ntimes 126 db 0\nalign 2,db 0\n.target:nop\nnop", SHORT),
    # A label attached to ALIGN denotes its input address, not its output.
    ("jmp target+2\ntimes 126 db 0\ntarget:align 2,db 0\nnop\nnop",
     b"\xe9\x80\x00" + bytes(127) + b"\x90\x90"),
    # NASM does not speculate on an EQU already evaluated in this pass.
    ("alias equ target+1\njmp alias\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\nnop",
     b"\xe9\x80\x00" + bytes(127) + b"\x90\x90"),
    ("alias equ other+1\nother equ target\njmp alias\ntimes 126 db 0\nalign 2,db 0\ntarget:nop\nnop",
     b"\xe9\x80\x00" + bytes(127) + b"\x90\x90"),
    # An unrelated equal-valued symbol must not turn a fixed target into a label.
    ("fixed equ 131\nanchor:nop\njmp anchor+131\ntimes 127 db 0\nnop",
     b"\x90\xe9\x7f\x00" + bytes(127) + b"\x90"),
)


class BranchLayoutDependencyTests(unittest.TestCase):
    def test_pinned_expression_layouts(self):
        for cpu in ("8086", "8088"):
            for body, expected in CASES:
                with self.subTest(cpu=cpu, body=body):
                    self.assertEqual(assemble(f"cpu {cpu}\nbits 16\n{body}\n",
                                              optimize=9, compatibility="nasm3"), expected)

    def test_expanded_macro_local_label(self):
        body = ("%macro block 0\njmp %%target+1\ntimes 126 db 0\n"
                "align 2,db 0\n%%target:nop\nnop\n%endmacro\nblock\nblock\n")
        for cpu in ("8086", "8088"):
            with self.subTest(cpu=cpu):
                self.assertEqual(assemble(f"cpu {cpu}\n" + body, optimize=9,
                                          compatibility="nasm3"), SHORT * 2)

    def test_reuse_clears_provenance_and_lists_final_bytes(self):
        asm = Assembler(optimize=9, compatibility="nasm3")
        for body, expected in CASES:
            self.assertEqual(asm.assemble("cpu 8088\n" + body), expected)
            self.assertEqual(b"".join(row.data for row in asm.listing), expected)
            with self.assertRaises(AssemblyError):
                asm.assemble("jmp undefined")
            self.assertEqual(asm.listing, ())
        self.assertEqual(asm.assemble("nop"), b"\x90")

    def test_affine_metadata_and_conservative_unknowns(self):
        positions = {"a": Value(100, symbolic=True, layout=((".text", 3, 1),)),
                     "b": Value(200, symbolic=True, layout=((".text", 7, 1),), forward=True)}
        cases = (("b+1", ((".text", 7, 1),)),
                 ("a+(b-a)", ((".text", 7, 1),)),
                 ("2*b-a", ((".text", 3, -1), (".text", 7, 2))),
                 ("~a+b", ((".text", 3, -1), (".text", 7, 1))),
                 ("b-b", ()), ("0*b", ()),
                 ("a*b", None), ("b&255", None), ("!b", None),
                 ("1 ? b : a", ((".text", 7, 1),)),
                 ("a ? b : a", None))
        for expression, expected in cases:
            with self.subTest(expression=expression):
                self.assertEqual(evaluate(expression, positions.__getitem__).layout, expected)
        self.assertTrue(evaluate("b+1", positions.__getitem__).forward)
        self.assertFalse(evaluate("a+1", positions.__getitem__).forward)


if __name__ == "__main__":
    unittest.main()
