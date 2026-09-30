"""Full deterministic 8086 boundary matrix, with retained failure reproducers."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pynasm import AssemblyError, assemble

try:
    from .integer_boundary_cases import legal_cases
    from .nasm_reference import reference, verify_version
except ImportError:
    from integer_boundary_cases import legal_cases
    from nasm_reference import reference, verify_version


def run(nasm: Path, *, cpu: str = "8086", full: bool = True,
        batch_size: int = 500, failures: Path = Path("integer-boundary-failures")) -> dict:
    if batch_size < 1 or cpu not in ("8086", "8088"):
        raise ValueError("positive batch size and an 8086/8088 CPU are required")
    nasm = nasm.resolve()
    version = verify_version(nasm)
    cases = list(legal_cases(full))
    compared = 0
    for level in (0, 1, 9):
        for start in range(0, len(cases), batch_size):
            batch = cases[start:start + batch_size]
            source = "cpu 8086\nbits 16\n" + "\n".join(c.source for c in batch) + "\n"
            expected = reference(nasm, source, level)
            error = None
            try:
                actual = assemble(source.replace("cpu 8086\n", f"cpu {cpu}\n", 1),
                                  compatibility="nasm3", optimize=level)
            except AssemblyError as exc:
                actual, error = None, str(exc)
            # This is a legal-input matrix: two rejections are a failure too.
            if expected is None or actual != expected:
                failures.mkdir(parents=True, exist_ok=True)
                stem = failures / f"O{level}-{cpu}-{start}"
                stem.with_suffix(".asm").write_text(source, encoding="ascii")
                for suffix, data in ((".expected.bin", expected), (".actual.bin", actual)):
                    if data is not None:
                        Path(str(stem) + suffix).write_bytes(data)
                metadata = {"version": version, "cpu": cpu, "level": level,
                            "first_case": start, "cases": len(batch),
                            "pynasm_error": error, "nasm_rejected": expected is None}
                stem.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
                raise AssertionError(f"integer boundary mismatch; reproducer: {stem}.asm")
            compared += len(batch)
    return {"cpu": cpu, "sources": len(cases), "comparisons": compared,
            "families": dict(Counter(c.family for c in cases))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--cpu", choices=("8086", "8088"), default="8086")
    parser.add_argument("--portable", action="store_true", help="run only the portable subset")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--failures", type=Path, default=Path("integer-boundary-failures"))
    args = parser.parse_args()
    print(json.dumps(run(args.nasm, cpu=args.cpu, full=not args.portable,
                         batch_size=args.batch_size, failures=args.failures), sort_keys=True))
