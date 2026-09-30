"""Portable, exact NASM 3.02 bytes and explicit CPU-boundary outcomes."""
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

from pynasm import AssemblyError, assemble
from integer_boundary_cases import CPU_PAIRS, legal_cases
from nasm_reference import OracleFailure, reference, verify_version
from nasm_template_inventory import NASM_COMMIT, SEMANTIC_SHA256

ROOT = Path(__file__).parent / "fixtures" / "generated"


class IntegerBoundaryTests(unittest.TestCase):
    def test_complete_template_ledger_and_integer_representatives(self):
        ledger = json.loads((ROOT / "nasm302_template_ledger.json").read_text())
        self.assertEqual(ledger["nasm_commit"], NASM_COMMIT)
        self.assertEqual(ledger["semantic_sha256"], SEMANTIC_SHA256)
        self.assertEqual(len(ledger["rows"]), 524)
        self.assertEqual(len({r["line"] for r in ledger["rows"]}), 524)
        self.assertEqual(Counter(r["scope"] for r in ledger["rows"]),
                         {"integer-8086": 337, "8087-deferred": 162,
                          "later-width-branch-excluded": 23, "optimizer-source32-open": 2})
        self.assertEqual(sum("OPT" in r["flags"] for r in ledger["rows"]), 8)
        for row in ledger["rows"]:
            if row["scope"] != "integer-8086":
                self.assertNotIn("expected", row)
                continue
            self.assertEqual(set(row["expected"]), {"0", "1", "9"})
            for level in (0, 1, 9):
                for cpu in ("8086", "8088"):
                    with self.subTest(row=row["line"], level=level, cpu=cpu):
                        expected = row["expected"][str(level)]
                        source = f"cpu {cpu}\nbits 16\n{row['case']}\n"
                        if expected is None:
                            self.assertIn("OPT", row["flags"])
                            self.assertIn(level, (0, 1))
                            with self.assertRaises(AssemblyError):
                                assemble(source, compatibility="nasm3", optimize=level)
                        else:
                            self.assertEqual(assemble(source, compatibility="nasm3", optimize=level),
                                             bytes.fromhex(expected))

    def test_integer_boundaries_at_all_optimization_levels(self):
        manifest = json.loads((ROOT / "integer_boundaries.json").read_text())
        cases = list(legal_cases())
        source = "cpu 8086\nbits 16\n" + "\n".join(c.source for c in cases) + "\n"
        self.assertEqual(len(cases), manifest["cases"])
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), manifest["source_sha256"])
        for level in (0, 1, 9):
            golden = manifest["goldens"][str(level)]
            expected = (ROOT / golden["file"]).read_bytes()
            self.assertEqual(len(expected), golden["size"])
            self.assertEqual(hashlib.sha256(expected).hexdigest(), golden["sha256"])
            for cpu in ("8086", "8088"):
                with self.subTest(level=level, cpu=cpu):
                    self.assertEqual(assemble(source.replace("cpu 8086\n", f"cpu {cpu}\n", 1),
                                              compatibility="nasm3", optimize=level), expected)

    def test_cpu_boundary_pairs_check_both_outcomes(self):
        manifest = json.loads((ROOT / "integer_boundaries.json").read_text())
        self.assertEqual([(p["control"], p["rejected"]) for p in manifest["cpu_pairs"]],
                         list(CPU_PAIRS))
        for pair in manifest["cpu_pairs"]:
            for cpu in ("8086", "8088"):
                for level in (0, 1, 9):
                    with self.subTest(pair=pair["rejected"], cpu=cpu, level=level):
                        self.assertEqual(assemble(f"cpu {cpu}\n{pair['control']}\n",
                                                  compatibility="nasm3", optimize=level),
                                         bytes.fromhex(pair["expected"][str(level)]))
                        with self.assertRaises(AssemblyError):
                            assemble(f"cpu {cpu}\n{pair['rejected']}\n",
                                     compatibility="nasm3", optimize=level)

    def test_strict_cpu_divergences_are_not_counted_as_parity(self):
        manifest = json.loads((ROOT / "integer_boundaries.json").read_text())
        self.assertTrue(manifest["strict_cpu_divergences"])
        for record in manifest["strict_cpu_divergences"]:
            self.assertEqual(record["pynasm"], "reject")
            self.assertTrue(record["nasm_bytes"].startswith("67"))
            for cpu in ("8086", "8088"):
                for level in (0, 1, 9):
                    with self.subTest(cpu=cpu, level=level), self.assertRaises(AssemblyError):
                        assemble(f"cpu {cpu}\n{record['source']}\n",
                                 compatibility="nasm3", optimize=level)


class OracleContractTests(unittest.TestCase):
    def test_crashes_timeouts_and_missing_output_are_not_rejections(self):
        for result in (CompletedProcess([], -11, "", "error: crash"),
                       CompletedProcess([], 2, "", "fatal"),
                       CompletedProcess([], 0, "", "")):
            with self.subTest(result=result), patch("nasm_reference.subprocess.run", return_value=result):
                with self.assertRaises(OracleFailure):
                    reference(Path("nasm"), "nop", 0)
        with patch("nasm_reference.subprocess.run", side_effect=TimeoutExpired("nasm", 5)):
            with self.assertRaises(OracleFailure):
                reference(Path("nasm"), "nop", 0)
        with patch("nasm_reference.subprocess.run", return_value=
                   CompletedProcess([], 1, "", "case.asm: error: invalid operands")):
            self.assertIsNone(reference(Path("nasm"), "bad", 0))

    def test_wrong_version_is_not_an_oracle(self):
        for version in ("NASM version 3.02.1", "NASM version 3.01", "not nasm"):
            with self.subTest(version=version), patch("nasm_reference.subprocess.run", return_value=
                   CompletedProcess([], 0, version, "")), self.assertRaises(OracleFailure):
                verify_version(Path("nasm"))


if __name__ == "__main__":
    unittest.main()
