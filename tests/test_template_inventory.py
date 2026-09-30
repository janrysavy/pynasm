"""The template reference pin must tolerate presentation, not semantic drift."""
import unittest
from pathlib import Path
from unittest.mock import patch

from nasm_template_inventory import (inventory, normalized_flags, parse_table,
                                     pinned_templates, semantic_digest)
from stress_templates import run
from pynasm import AssemblyError


class TemplateInventoryTests(unittest.TestCase):
    def test_perl_flag_order_and_range_spellings_are_equivalent(self):
        first = b"MOV reg16,imm16 [ri: o16 b8+r iw] SM0-1,ND,8086\n"
        second = b"; harmless comment\nMOV  reg16,imm16 [ri:  o16 b8+r iw] SM1,8086,SM0,ND\n"
        digest = semantic_digest(parse_table(first))
        self.assertEqual(digest, semantic_digest(parse_table(second)))
        # Exercise the public pin check rather than only the normalizer.
        with patch("nasm_template_inventory.SEMANTIC_SHA256", digest):
            self.assertEqual(len(pinned_templates(first)), 1)
            self.assertEqual(len(pinned_templates(second)), 1)
            for altered in (second.replace(b"b8+r", b"b0+r"),
                            second.replace(b"8086", b"386"),
                            second.replace(b"SM1,", b""),
                            second.replace(b"imm16", b"imm8")):
                with self.subTest(altered=altered), self.assertRaises(ValueError):
                    pinned_templates(altered)

    def test_inventory_retains_optimizer_and_deferred_rows(self):
        table = (b"NOP void [90] 8086\n"
                 b"BSWAP reg_ax [86 c4] 8086,OPT\n"
                 b"FADD fpureg [d8 c0+r] 8086,FPU\n"
                 b"JMP imm32|near [e9 id] 8086\n"
                 b"MOVZX reg16,rm32 [8b /r] 8086,OPT\n")
        with patch("nasm_template_inventory.SEMANTIC_SHA256",
                   semantic_digest(parse_table(table))):
            rows = inventory(table)["rows"]
        self.assertEqual([r["scope"] for r in rows],
                         ["integer-8086", "integer-8086", "8087-deferred",
                          "later-width-branch-excluded", "optimizer-source32-open"])
        self.assertIn("OPT", rows[1]["flags"])

    def test_legal_matrix_must_not_pass_when_both_assemblers_reject(self):
        from subprocess import CompletedProcess
        with patch("stress_templates.rows", return_value=[(1, "NOP", "void")]), \
             patch.object(Path, "read_bytes", return_value=b""), \
             patch("stress_templates.subprocess.run", return_value=
                   CompletedProcess([], 1, "", "error: rejected")), \
             patch("stress_templates.assemble", side_effect=AssemblyError("rejected")):
            with self.assertRaisesRegex(AssertionError, "NASM rejected legal template"):
                run(Path("unused.dat"), Path("unused-nasm"), workers=1)

    def test_pin_rejects_malformed_input(self):
        with self.assertRaisesRegex(ValueError, "malformed"):
            parse_table(b"MOV ax\n")
        with self.assertRaisesRegex(ValueError, "invalid NASM flag range"):
            normalized_flags("SM9-0")
        with self.assertRaises(ValueError):
            pinned_templates(b"NOP void [90] 8086\n")


if __name__ == "__main__":
    unittest.main()
