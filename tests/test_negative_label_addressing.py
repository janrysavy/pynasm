"""Native NASM3 negative-section address compatibility (PR #11, now repaired).

Based displacement selection uses section offsets; direct and word addresses
retain the absolute expression. This is NASM compatibility, not a claim about
the desired mathematical address. See doc/PR_REVIEW_20260930.md.
"""
import unittest
from pynasm import assemble


class NegativeLabelAddressingTests(unittest.TestCase):
    def test_based_negative_label_matches_native_nasm(self):
        for cpu in ('8086', '8088'):
            for expression in ('-target', 'target*-1', '-1*target'):
                with self.subTest(cpu=cpu, expression=expression):
                    source = (f'cpu {cpu}\norg 256\ntarget:nop\n'
                              f'mov ax,[bx+({expression})]\n')
                    # NASM 3.02 -O9: 90 8B 07 (not BX-256).
                    self.assertEqual(assemble(source, compatibility='nasm3', optimize=9),
                                     bytes.fromhex('90 8b 07'))

    def test_direct_and_positive_label_guards(self):
        for cpu in ('8086', '8088'):
            for operand, expected in (('[-target]', '90 a1 00 ff'),
                                      ('[bx+target]', '90 8b 87 00 01')):
                with self.subTest(cpu=cpu, operand=operand):
                    source=f'cpu {cpu}\norg 256\ntarget:nop\nmov ax,{operand}\n'
                    self.assertEqual(assemble(source, compatibility='nasm3', optimize=9),
                                     bytes.fromhex(expected))


if __name__ == '__main__':
    unittest.main()
