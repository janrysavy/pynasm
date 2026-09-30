import gzip
import json
import os
from pathlib import Path
import unittest

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version


class ExpressionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parent / 'fixtures/generated/expression_recovery.json.gz'
        cls.receipt = json.loads(gzip.decompress(path.read_bytes()))

    def test_captured_native_outcomes(self):
        assembler = Assembler(compatibility='nasm3')
        for row in self.receipt['cases']:
            with self.subTest(group=row['group'], source=row['source'], level=row['level']):
                assembler.optimize = row['level']
                try:
                    actual = assembler.assemble(row['source']).hex()
                except AssemblyError:
                    actual = None
                self.assertEqual(actual, row['hex'])
        # A refused input must not contaminate a reused instance.
        self.assertEqual(assembler.assemble('cpu 8088\nnop\n'), b'\x90')

    @unittest.skipUnless(os.environ.get('NASM'), 'optional pinned live NASM oracle')
    def test_native_receipt_replay(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for row in self.receipt['cases']:
            with self.subTest(source=row['source'], level=row['level']):
                expected = reference(native, row['source'], row['level'])
                self.assertEqual(None if expected is None else expected.hex(), row['hex'])
