"""Assembly-aware preprocessor conditions, checked against NASM 3.02."""
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings

from pynasm import Assembler, AssemblyError
from nasm_reference import reference, verify_version

FIXTURE = Path(__file__).parent / "fixtures/preprocessor_location.json.gz"
ROWS = json.loads(gzip.decompress(FIXTURE.read_bytes()))["cases"]


def local_result(row):
    with tempfile.TemporaryDirectory() as directory:
        for name, data in row["files"].items():
            (Path(directory) / name).write_bytes(data.encode("ascii"))
        asm = Assembler(compatibility="nasm3", optimize=row["level"],
                        include_paths=[directory])
        try:
            result = asm.assemble(row["source"])
        except AssemblyError:
            return None
        # Listing bytes must describe the same final conditional expansion.
        for line in asm.listing:
            if line.file_offset is not None:
                assert line.data == result[line.file_offset:line.file_offset + line.size]
        return result.hex()


class PreprocessorLocationTests(unittest.TestCase):
    def test_pinned_location_context_matrix(self):
        self.assertEqual(len(ROWS), 294)
        self.assertEqual(sum(row["hex"] is not None for row in ROWS), 234)
        for row in ROWS:
            with self.subTest(name=row["name"], cpu=row["cpu"], level=row["level"]):
                self.assertEqual(local_result(row), row["hex"])

    @unittest.skipUnless(os.environ.get("NASM"), "optional NASM 3.02 oracle")
    def test_live_reference_matches_pinned_matrix(self):
        nasm = Path(os.environ["NASM"])
        verify_version(nasm)
        for row in ROWS:
            with self.subTest(name=row["name"], cpu=row["cpu"], level=row["level"]):
                # NASM spells the shared instruction set 8086; pynasm also
                # accepts 8088 as an alias. Do not count NASM's alias rejection.
                expected = reference(nasm, row["source"].replace("cpu 8088", "cpu 8086"),
                                     row["level"], files={name: data.encode("ascii")
                                     for name, data in row["files"].items()})
                self.assertEqual(None if expected is None else expected.hex(), row["hex"])
                self.assertEqual(local_result(row), row["hex"])

    def test_branch_optimization_reprocesses_conditions_and_listing(self):
        source = "jmp end\n%if $-$$=2\ndb 1\n%else\ndb 2\n%endif\nend: nop\n"
        for level, expected in ((0, "e901000290"), (1, "e901000290"), (9, "eb010190")):
            asm = Assembler(compatibility="nasm3", optimize=level)
            self.assertEqual(asm.assemble(source).hex(), expected)
            self.assertIn("db 1" if level == 9 else "db 2", [line.text for line in asm.listing])
            self.assertNotIn("db 2" if level == 9 else "db 1", [line.text for line in asm.listing])

    def test_warning_events_come_from_final_pass_and_keep_repetitions(self):
        source = ("%rep 2\n%warning repeated\n%endrep\njmp end\n"
                  "%if $-$$=2\n%warning short\n%else\n%warning long\n%endif\nend: nop\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Assembler(compatibility="nasm3", optimize=9).assemble(source)
        self.assertEqual([str(item.message).split(": ", 1)[1] for item in caught],
                         ["repeated", "repeated", "short"])

    def test_reuse_after_relocated_condition_failure(self):
        asm = Assembler(compatibility="nasm3", optimize=9)
        for source in ("%if $\ndb 1\n%endif\n", "a: nop\nabsolute a\n%if $\n%endif\n"):
            with self.assertRaises(AssemblyError):
                asm.assemble(source)
            self.assertEqual(asm.listing, ())
            self.assertEqual(asm.assemble("absolute 32\n%assign n $\nsection .text\ndb n\n"), b" ")


if __name__ == "__main__":
    unittest.main()
