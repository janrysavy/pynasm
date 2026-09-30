"""Retain section identity independently of layout/optimization provenance."""
import gzip
import json
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version


class ExpressionProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads(gzip.decompress((Path(__file__).parent /
            'fixtures/generated/expression_provenance.json.gz').read_bytes()))

    def test_captured_native_outcomes(self):
        assembler = Assembler(compatibility='nasm3')
        for row in self.receipt['cases']:
            for cpu in ('8086', '8088'):
                with self.subTest(cpu=cpu, source=row['source'], level=row['level']):
                    assembler.optimize = row['level']
                    source = row['source'].replace('cpu 8086', f'cpu {cpu}', 1)
                    if row['hex'] is None:
                        with self.assertRaises(AssemblyError):
                            assembler.assemble(source)
                    else:
                        self.assertEqual(assembler.assemble(source).hex(), row['hex'])
        # Reset both successful and refused inputs, including cached EQU bases.
        self.assertEqual(assembler.assemble('cpu 8088\nnop\n'), b'\x90')

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_native_receipt_replay(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for row in self.receipt['cases']:
            with self.subTest(source=row['source'], level=row['level']):
                binary = reference(native, row['source'], row['level'])
                self.assertEqual(None if binary is None else binary.hex(), row['hex'])
