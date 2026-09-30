"""Regenerate whole-program source/input/byte fixtures with the pinned oracle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .nasm_reference import reference, verify_version
    from .nasm_template_inventory import NASM_COMMIT
    from .program_interactions import (PORTABLE_COUNT, PORTABLE_SEED, REFERENCE_EXCLUSIONS,
                                       Program, interaction_programs, rejected_programs)
except ImportError:
    from nasm_reference import reference, verify_version
    from nasm_template_inventory import NASM_COMMIT
    from program_interactions import (PORTABLE_COUNT, PORTABLE_SEED, REFERENCE_EXCLUSIONS,
                                      Program, interaction_programs, rejected_programs)

ROOT = Path(__file__).parent / "fixtures" / "generated" / "layout_interactions"


def minimized_alignment_programs():
    # Minimized from the copy-data-bss interaction family, seed 20260930,
    # case 56. Preserve the actual source beside its pinned NASM bytes.
    for section, data, alignment in ((".bss", "resb 1", "alignb 32"),
                                     (".data", "db 1", "align 32,db 0")):
        yield Program("late-alignment" + section, "late-alignment-regression",
                      "cpu 8086\nbits 16\nmov ax,item\n"
                      f"section {section} align=16\nitem: {data}\n{alignment}\n", {})


def build(nasm: Path, output: Path = ROOT) -> dict:
    nasm = nasm.resolve()
    verify_version(nasm)
    output.mkdir(parents=True, exist_ok=True)
    positive = list(interaction_programs(PORTABLE_COUNT, PORTABLE_SEED))
    positive.extend(minimized_alignment_programs())
    negative = list(rejected_programs())
    manifest = {"schema": 1, "nasm_commit": NASM_COMMIT, "seed": PORTABLE_SEED,
                "generated_programs": PORTABLE_COUNT, "records": [], "reference_exclusions": []}
    for reject, programs in ((False, positive), (True, negative)):
        for program in programs:
            source_bytes = program.source.encode("ascii")
            record = {"name": program.name, "family": program.family,
                      "file": program.name + ".asm", "reject": reject,
                      "sha256": hashlib.sha256(source_bytes).hexdigest(),
                      "inputs": {name: data.hex() for name, data in program.files.items()},
                      "expected": {}}
            for level in (0, 1, 9):
                data = reference(nasm, program.source, level, files=program.files)
                if (data is None) != reject:
                    raise AssertionError(f"unexpected NASM outcome: {program.name}, O{level}")
                record["expected"][str(level)] = None if reject else data.hex()
            (output / record["file"]).write_bytes(source_bytes)
            manifest["records"].append(record)
    # Known reference hangs are deliberately never passed to reference().
    for name, body in REFERENCE_EXCLUSIONS.items():
        source = "cpu 8086\nbits 16\n" + body
        (output / (name + ".asm")).write_text(source, encoding="ascii")
        manifest["reference_exclusions"].append(
            {"name": name, "file": name + ".asm", "sha256": hashlib.sha256(source.encode()).hexdigest(),
             "reason": "NASM 3.02 times out at O0/O1/O9 with a 5-second limit",
             "pynasm": "reject; not a byte-parity claim"})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
    return {"positive": len(positive), "negative": len(negative),
            "reference_exclusions": len(REFERENCE_EXCLUSIONS)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.nasm, args.output), sort_keys=True))
