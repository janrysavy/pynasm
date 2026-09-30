"""Location-dependent data sizes must participate in 8086 branch relaxation."""
import unittest
from pynasm import Assembler, AssemblyError, assemble


class VariablePaddingTests(unittest.TestCase):
    def test_fixed_target_does_not_follow_a_shortening_jump(self):
        for cpu in ("8086", "8088"):
            for padding in ("times 130-($-$$) db 0", "resb 130-($-$$)",
                            "db (130-($-$$)) dup (0)"):
                with self.subTest(cpu=cpu, padding=padding):
                    source = f"cpu {cpu}\njmp target\n{padding}\ntarget:nop\n"
                    self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"),
                                     bytes.fromhex("e9 7f 00") + bytes(127) + b"\x90")

    def test_fitting_dynamic_target_still_uses_short_form(self):
        for target in (127, 128, 129):
            for cpu in ("8086", "8088"):
                with self.subTest(cpu=cpu, target=target):
                    source = f"cpu {cpu}\njmp done\ntimes {target}-($-$$) db 0\ndone:nop"
                    self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"),
                                     bytes((0xEB, target-2)) + bytes(target-2) + b"\x90")

    def test_data_list_and_nested_repeat_sizes(self):
        for cpu in ("8086", "8088"):
            for padding in ("db 0, (129-($-$$)) dup (0)",
                            "times 1 db (130-($-$$)) dup (0)",
                            "db 1 dup ((130-($-$$)) dup (0), 0)"):
                with self.subTest(cpu=cpu, padding=padding):
                    # The last variant has one extra trailing byte.
                    extra = int(padding.startswith("db 1 dup"))
                    source = f"cpu {cpu}\njmp done\n{padding}\ndone:nop"
                    self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"),
                                     bytes((0xE9, 127+extra, 0)) + bytes(127+extra) + b"\x90")

    def test_reuse_and_explicit_short_validation(self):
        asm = Assembler(optimize=9, compatibility="nasm3")
        source = "cpu 8088\njmp done\nresb 130-($-$$)\ndone:nop"
        expected = b"\xe9\x7f\x00" + bytes(127) + b"\x90"
        self.assertEqual(asm.assemble(source), expected)
        self.assertEqual(b"".join(row.data for row in asm.listing), expected)
        with self.assertRaisesRegex(AssemblyError, "out of range"):
            asm.assemble(source.replace("jmp done", "jmp short done"))
        self.assertEqual(asm.assemble("jmp done\ndone:nop"), b"\xeb\x00\x90")


if __name__ == "__main__":
    unittest.main()
