"""Live whole-program interactions with retained, self-contained reproducers."""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from pynasm import Assembler, AssemblyError

try:
    from .nasm_reference import reference, verify_version
    from .program_interactions import interaction_programs
except ImportError:
    from nasm_reference import reference, verify_version
    from program_interactions import interaction_programs


def write_inputs(root: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        path = root / name
        if root.resolve() not in path.resolve().parents:
            raise ValueError("program input must stay inside its workspace")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def assemble_program(source: str, files: dict[str, bytes], level: int, cpu: str) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_inputs(root, files)
        return Assembler(compatibility="nasm3", optimize=level, include_paths=[root]).assemble(
            source.replace("cpu 8086\n", f"cpu {cpu}\n", 1), filename=str(root / "case.asm"))


def run(nasm: Path, count: int = 120, seed: int = 20260930, cpu: str = "8086",
        failures: Path = Path("program-layout-failures")) -> dict:
    if cpu not in ("8086", "8088") or count < 0:
        raise ValueError("an 8086/8088 CPU and a nonnegative count are required")
    nasm = nasm.resolve()
    version = verify_version(nasm)
    compared = 0
    families = Counter()
    for program in interaction_programs(count, seed):
        families[program.family] += 1
        for level in (0, 1, 9):
            expected = reference(nasm, program.source, level, files=program.files)
            error = None
            try:
                actual = assemble_program(program.source, program.files, level, cpu)
            except AssemblyError as exc:
                actual, error = None, str(exc)
            if expected is None or actual != expected:
                root = failures / f"{seed}-{program.name}-{cpu}-O{level}"
                root.mkdir(parents=True, exist_ok=True)
                write_inputs(root, program.files)
                (root / "case.asm").write_text(program.source, encoding="ascii")
                for name, data in (("expected.bin", expected), ("actual.bin", actual)):
                    if data is not None:
                        (root / name).write_bytes(data)
                metadata = {"cpu": cpu, "optimization": level, "seed": seed,
                            "case": program.name, "family": program.family,
                            "nasm": version, "nasm_rejected": expected is None,
                            "pynasm_error": error}
                (root / "context.json").write_text(json.dumps(metadata, indent=2) + "\n")
                raise AssertionError(f"whole-program mismatch; reproducer retained in {root}")
            compared += 1
    return {"programs": count, "comparisons": compared, "seed": seed, "cpu": cpu,
            "families": dict(families)}
