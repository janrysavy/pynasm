"""Regenerate the new template ledger and integer-boundary bytes using NASM 3.02."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .integer_boundary_cases import CPU_PAIRS, STRICT_CPU_DIVERGENCES, legal_cases
    from .nasm_reference import reference, verify_version
    from .nasm_template_inventory import inventory
    from .stress_templates import case_for
except ImportError:
    from integer_boundary_cases import CPU_PAIRS, STRICT_CPU_DIVERGENCES, legal_cases
    from nasm_reference import reference, verify_version
    from nasm_template_inventory import inventory
    from stress_templates import case_for

ROOT = Path(__file__).parent / "fixtures" / "generated"


def build(expanded: Path, nasm: Path, output: Path = ROOT) -> dict:
    nasm = nasm.resolve()
    verify_version(nasm)
    ledger = inventory(expanded.read_bytes())
    for row in ledger["rows"]:
        if row["scope"] != "integer-8086":
            continue
        source = case_for(row["mnemonic"], row["operands"])
        row["case"] = source
        row["expected"] = {}
        for level in (0, 1, 9):
            actual = reference(nasm, f"cpu 8086\nbits 16\n{source}\n", level)
            should_reject = "OPT" in row["flags"] and level <= 1
            if (actual is None) != should_reject:
                raise AssertionError(f"unexpected oracle result for row {row['line']} O{level}")
            row["expected"][str(level)] = None if should_reject else actual.hex()
    output.mkdir(parents=True, exist_ok=True)
    # One record per line makes regenerated ledger diffs reviewable.
    header = {k: v for k, v in ledger.items() if k != "rows"}
    text = json.dumps(header, indent=2)[:-2] + ',\n  "rows": [\n'
    text += ",\n".join("    " + json.dumps(row, separators=(",", ":"))
                        for row in ledger["rows"])
    (output / "nasm302_template_ledger.json").write_text(text + "\n  ]\n}\n", encoding="ascii")
    sources = [case.source for case in legal_cases()]
    source = "cpu 8086\nbits 16\n" + "\n".join(sources) + "\n"
    manifest = {"schema": 1, "nasm_commit": ledger["nasm_commit"],
                "mode": "portable", "cases": len(sources),
                "source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
                "goldens": {}, "cpu_pairs": [], "strict_cpu_divergences": []}
    for level in (0, 1, 9):
        data = reference(nasm, source, level)
        if data is None:
            raise AssertionError("NASM rejected a legal integer-boundary program")
        name = f"integer_boundaries.O{level}.bin"
        (output / name).write_bytes(data)
        manifest["goldens"][str(level)] = {"file": name, "size": len(data),
                                           "sha256": hashlib.sha256(data).hexdigest()}
    for control, rejected in CPU_PAIRS:
        expected = {}
        for level in (0, 1, 9):
            data = reference(nasm, f"cpu 8086\n{control}\n", level)
            if data is None or reference(nasm, f"cpu 8086\n{rejected}\n", level) is not None:
                raise AssertionError(f"invalid CPU-boundary pair: {control!r} / {rejected!r}")
            expected[str(level)] = data.hex()
        manifest["cpu_pairs"].append({"control": control, "rejected": rejected,
                                      "expected": expected})
    for source, expected in STRICT_CPU_DIVERGENCES:
        for level in (0, 1, 9):
            if reference(nasm, f"cpu 8086\n{source}\n", level) != bytes.fromhex(expected):
                raise AssertionError(f"changed reference divergence: {source}")
        manifest["strict_cpu_divergences"].append(
            {"source": source, "nasm_bytes": expected, "pynasm": "reject",
             "reason": "32-bit effective address requires a later CPU"})
    (output / "integer_boundaries.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                    encoding="ascii")
    return {"inventory_rows": len(ledger["rows"]), "integer_cases": len(sources),
            "cpu_pairs": len(CPU_PAIRS)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded", required=True, type=Path)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.expanded, args.nasm, args.output), sort_keys=True))
