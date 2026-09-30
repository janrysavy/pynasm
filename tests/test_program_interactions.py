"""Portable whole-program checks with explicit legal, illegal and excluded sets."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pynasm import AssemblyError, assemble
from build_program_fixtures import build, minimized_alignment_programs
from nasm_template_inventory import NASM_COMMIT
from program_interactions import (PORTABLE_COUNT, PORTABLE_SEED, REFERENCE_EXCLUSIONS,
                                  Program, interaction_programs, rejected_programs)
from stress_program_interactions import assemble_program, run

ROOT = Path(__file__).parent / "fixtures" / "generated" / "layout_interactions"


class ProgramInteractionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="ascii"))
        self.assertEqual(self.manifest["nasm_commit"], NASM_COMMIT)

    def source(self, record):
        data = (ROOT / record["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
        return data.decode("ascii")

    def test_complete_program_bytes_across_sections_and_inputs(self):
        records = [r for r in self.manifest["records"] if not r["reject"]]
        self.assertEqual(len(records), 26)
        for record in records:
            source = self.source(record)
            files = {name: bytes.fromhex(data) for name, data in record["inputs"].items()}
            for level in (0, 1, 9):
                expected = record["expected"][str(level)]
                self.assertIsNotNone(expected, "legal cases require accepted bytes")
                for cpu in ("8086", "8088"):
                    with self.subTest(case=record["name"], cpu=cpu, level=level):
                        self.assertEqual(assemble_program(source, files, level, cpu),
                                         bytes.fromhex(expected))

    def test_declared_layout_rejections(self):
        records = [r for r in self.manifest["records"] if r["reject"]]
        self.assertEqual(len(records), 6)
        for record in records:
            source = self.source(record)
            for level in (0, 1, 9):
                self.assertIsNone(record["expected"][str(level)])
                for cpu in ("8086", "8088"):
                    with self.subTest(case=record["name"], cpu=cpu, level=level):
                        with self.assertRaises(AssemblyError):
                            assemble_program(source, {}, level, cpu)

    def test_reference_hang_has_separate_pynasm_rejection_guard(self):
        exclusions = self.manifest["reference_exclusions"]
        self.assertEqual(len(exclusions), 1)
        self.assertEqual({r["name"] for r in exclusions}, set(REFERENCE_EXCLUSIONS))
        for record in exclusions:
            source = self.source(record)
            for cpu in ("8086", "8088"):
                for level in (0, 1, 9):
                    with self.subTest(cpu=cpu, level=level), self.assertRaisesRegex(AssemblyError, "cyclic"):
                        assemble(source.replace("cpu 8086\n", f"cpu {cpu}\n", 1),
                                 compatibility="nasm3", optimize=level)

    def test_pinned_sources_match_deterministic_generator(self):
        generated = list(interaction_programs(PORTABLE_COUNT, PORTABLE_SEED))
        self.assertEqual(self.manifest["seed"], PORTABLE_SEED)
        self.assertEqual(self.manifest["generated_programs"], PORTABLE_COUNT)
        self.assertEqual(generated, list(interaction_programs(PORTABLE_COUNT, PORTABLE_SEED)))
        self.assertNotEqual(generated, list(interaction_programs(PORTABLE_COUNT, PORTABLE_SEED + 1)))
        generated += list(minimized_alignment_programs()) + list(rejected_programs())
        self.assertEqual(len(generated), len(self.manifest["records"]))
        for program, record in zip(generated, self.manifest["records"]):
            self.assertEqual(program.name, record["name"])
            self.assertEqual(program.source, self.source(record))
            self.assertEqual(program.files, {n: bytes.fromhex(v) for n, v in record["inputs"].items()})

    def test_fixture_generator_never_runs_known_reference_hang(self):
        negative = {p.source for p in rejected_programs()}
        excluded = {"cpu 8086\nbits 16\n" + s for s in REFERENCE_EXCLUSIONS.values()}
        calls = []
        def fake_reference(nasm, source, level, **kwargs):
            self.assertNotIn(source, excluded)
            calls.append((source, level))
            return None if source in negative else b"\x90"
        with tempfile.TemporaryDirectory() as directory, \
             patch("build_program_fixtures.verify_version"), \
             patch("build_program_fixtures.reference", side_effect=fake_reference):
            summary = build(Path("unused-nasm"), Path(directory))
        self.assertEqual(summary, {"positive": 26, "negative": 6, "reference_exclusions": 1})
        self.assertEqual(len(calls), 96)

    def test_live_mismatch_retains_source_inputs_and_outcomes(self):
        program = Program("probe", "guard", "cpu 8086\nnop\n",
                          {"nested/include.bin": b"abc"})
        for expected, actual in ((None, None), (b"\x90", b"\xcc")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory, \
                 patch("stress_program_interactions.verify_version", return_value="NASM 3.02"), \
                 patch("stress_program_interactions.interaction_programs", return_value=[program]), \
                 patch("stress_program_interactions.reference", return_value=expected), \
                 patch("stress_program_interactions.assemble_program") as sut:
                if actual is None:
                    sut.side_effect = AssemblyError("rejected")
                else:
                    sut.return_value = actual
                with self.assertRaisesRegex(AssertionError, "reproducer retained"):
                    run(Path("unused"), count=1, seed=123, cpu="8088", failures=Path(directory))
                root = Path(directory) / "123-probe-8088-O0"
                self.assertEqual((root / "case.asm").read_text(), program.source)
                self.assertEqual((root / "nested/include.bin").read_bytes(), b"abc")
                context = json.loads((root / "context.json").read_text())
                self.assertEqual(context["nasm_rejected"], expected is None)
                self.assertEqual(context["cpu"], "8088")
                if expected is not None:
                    self.assertEqual((root / "expected.bin").read_bytes(), expected)
                    self.assertEqual((root / "actual.bin").read_bytes(), actual)


if __name__ == "__main__":
    unittest.main()
