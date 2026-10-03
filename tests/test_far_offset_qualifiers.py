"""Far immediate syntax captured independently from NASM 3.02."""
import json
import os
from pathlib import Path
import unittest

from pynasm import AssemblyError, assemble
from nasm_reference import reference, verify_version


class FarOffsetQualifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).parent / 'fixtures/generated/far_offset_qualifiers.json'
        cls.cases = json.loads(fixture.read_text(encoding='ascii'))['cases']

    def test_native_captured_acceptance_and_bytes(self):
        for row in self.cases:
            for level in (0, 1, 9):
                for cpu in ('8086', '8088'):
                    with self.subTest(source=row['source'], level=level, cpu=cpu):
                        source = row['source'].replace('cpu 8086', 'cpu ' + cpu)
                        try:
                            actual = assemble(source, compatibility='nasm3', optimize=level).hex()
                        except AssemblyError:
                            actual = None
                        self.assertEqual(actual, row['hex'])

    @unittest.skipUnless(os.environ.get('NASM'), 'optional NASM 3.02 oracle')
    def test_live_native_receipt(self):
        native = Path(os.environ['NASM'])
        verify_version(native)
        for row in self.cases:
            for level in (0, 1, 9):
                with self.subTest(source=row['source'], level=level):
                    data = reference(native, row['source'], level)
                    self.assertEqual(None if data is None else data.hex(), row['hex'])
