"""Independent NASM 3.02 outcomes captured before the production repair."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from pynasm import AssemblyError, assemble


class NegativeAddressMatrixTests(unittest.TestCase):
    def test_native_section_offset_matrix(self):
        fixture = Path(__file__).parent / 'fixtures/generated/negative_addresses.json.gz'
        receipt = json.loads(gzip.decompress(fixture.read_bytes()))
        self.assertEqual(receipt['native_sha256'],
                         '04ec2385879f7e1c45dbe76c4020970555de48eeb97c23f59620ede061328f51')
        self.assertEqual(len(receipt['cases']), 1644)
        self.assertEqual(sum(c['native_hex'] is None for c in receipt['cases']), 6)
        for case in receipt['cases']:
            for cpu in ('8086', '8088'):
                source = case['source'].replace('cpu 8086\n', f'cpu {cpu}\n', 1)
                with self.subTest(cpu=cpu, source=source, level=case['optimization']):
                    if case['native_hex'] is None:
                        with self.assertRaises(AssemblyError):
                            assemble(source, compatibility='nasm3', optimize=case['optimization'])
                    else:
                        self.assertEqual(assemble(source, compatibility='nasm3',
                                                  optimize=case['optimization']),
                                         bytes.fromhex(case['native_hex']))

    def test_historical_profile_keeps_mathematical_displacement(self):
        self.assertEqual(assemble('org 256\ntarget:nop\nmov ax,[bx-target]\n'),
                         bytes.fromhex('90 8b 87 00 ff'))

    def test_fixture_has_independent_source_identity(self):
        fixture = Path(__file__).parent / 'fixtures/generated/negative_addresses.json.gz'
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), FIXTURE_SHA256)


FIXTURE_SHA256 = 'c7c04d673f1718d046563cecbd56a87d4f585aa7ae16f61d42df659f0cd2bf4d'
