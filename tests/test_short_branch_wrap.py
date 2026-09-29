"""8086 rel8 validation uses wrapping IP arithmetic, not an unbounded integer."""
import unittest

from pynasm import AssemblyError, assemble


BRANCHES = (("jmp short", 0xEB), ("jo short", 0x70), ("jno short", 0x71),
            ("jb short", 0x72), ("jae short", 0x73), ("je short", 0x74),
            ("jne short", 0x75), ("jbe short", 0x76), ("ja short", 0x77),
            ("js short", 0x78), ("jns short", 0x79), ("jp short", 0x7A),
            ("jnp short", 0x7B), ("jl short", 0x7C), ("jge short", 0x7D),
            ("jle short", 0x7E), ("jg short", 0x7F), ("loopne", 0xE0),
            ("loope", 0xE1), ("loop", 0xE2), ("jcxz", 0xE3))


class ShortBranchWrapTests(unittest.TestCase):
    def test_equ_target_at_wrapped_next_ip(self):
        for cpu in ("8086", "8088"):
            for profile in ("nasm09839", "nasm3"):
                for level in (0, 1, 9):
                    for prefix, prefix_bytes in (("", b""), ("es ", b"\x26")):
                        for mnemonic, opcode in BRANCHES:
                            with self.subTest(cpu=cpu, profile=profile, level=level,
                                              prefix=prefix, mnemonic=mnemonic):
                                origin = 65534 - len(prefix_bytes)
                                source = (f"cpu {cpu}\nbits 16\norg {origin}\n"
                                          f"target equ 0\n{prefix}{mnemonic} target\n")
                                self.assertEqual(assemble(source, optimize=level,
                                                          compatibility=profile),
                                                 prefix_bytes + bytes((opcode, 0)))

    def test_same_section_label_at_wrapped_next_ip(self):
        for cpu in ("8086", "8088"):
            for profile in ("nasm09839", "nasm3"):
                with self.subTest(cpu=cpu, profile=profile):
                    source = f"cpu {cpu}\nstart:nop\ntimes 65533 db 0\nloop start\n"
                    self.assertEqual(assemble(source, compatibility=profile),
                                     b"\x90" + bytes(65533) + b"\xe2\x00")

    def test_real_out_of_range_short_branches_still_fail(self):
        for cpu in ("8086", "8088"):
            for profile in ("nasm09839", "nasm3"):
                for mnemonic, _ in BRANCHES:
                    for body in (f"{mnemonic} target\ntimes 128 db 0\ntarget:nop",
                                 f"target:nop\ntimes 126 db 0\n{mnemonic} target"):
                        with self.subTest(cpu=cpu, profile=profile, source=body):
                            with self.assertRaisesRegex(AssemblyError, "out of range"):
                                assemble(f"cpu {cpu}\n{body}\n", compatibility=profile)

    def test_automatic_encoding_selection_remains_nasm_compatible(self):
        # This fix validates an already selected short form. It must not
        # introduce wrap-aware shortening that NASM itself does not perform.
        for profile in ("nasm09839", "nasm3"):
            for mnemonic, expected in (("jmp", "e9 ff ff"), ("jz", "75 03 e9 fd ff")):
                with self.subTest(profile=profile, mnemonic=mnemonic):
                    source = f"cpu 8088\norg 65534\ntarget equ 0\n{mnemonic} target\n"
                    self.assertEqual(assemble(source, optimize=9, compatibility=profile),
                                     bytes.fromhex(expected))


if __name__ == "__main__":
    unittest.main()
