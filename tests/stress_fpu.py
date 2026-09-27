"""Differential all pinned 8087 rows across registers and 8086 addresses."""

import argparse
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler
from pynasm.fpu8087 import FPU_FIXED, FPU_MEMORY, FPU_REGISTER


SIZES = {16: "word", 32: "dword", 64: "qword", 80: "tword"}
BASES = ("bx", "bp", "si", "di", "bx+si", "bx+di", "bp+si", "bp+di")
DISPLACEMENTS = (-129, -128, -1, 0, 1, 127, 128)
SEGMENTS = ("", "es:", "ss:")


def cases():
    yield from sorted(FPU_FIXED)
    for mnemonic, forms in sorted(FPU_MEMORY.items()):
        for width in sorted(forms, key=lambda value: -1 if value is None else value):
            qualifier = SIZES[width] + " " if width else ""
            for base, displacement, segment in itertools.product(BASES, DISPLACEMENTS, SEGMENTS):
                yield f"{mnemonic} {qualifier}[{segment}{base}+{displacement}]"
    for mnemonic, forms in sorted(FPU_REGISTER.items()):
        for form in sorted(forms):
            for index in range(8):
                operand = {"fpureg": f"st{index}", "fpureg|to": f"to st{index}",
                           "fpureg,fpu0": f"st{index},st0",
                           "fpu0,fpureg": f"st0,st{index}"}[form]
                yield f"{mnemonic} {operand}"


def run(nasm: Path, batch_size: int = 1200) -> int:
    generated = iter(cases())
    compared = 0
    with tempfile.TemporaryDirectory() as directory:
        source_file = Path(directory) / "fpu.asm"
        output_file = Path(directory) / "fpu.bin"
        while batch := list(itertools.islice(generated, batch_size)):
            source = "cpu 8086\n" + "\n".join(batch) + "\n"
            source_file.write_text(source, encoding="ascii")
            for level in (0, 9):
                reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}", "-o",
                                            str(output_file), str(source_file)],
                                           capture_output=True, text=True, timeout=10)
                if reference.returncode:
                    raise RuntimeError(reference.stderr)
                actual = Assembler(optimize=level, compatibility="nasm3").assemble(source)
                expected = output_file.read_bytes()
                if actual != expected:
                    offset = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b),
                                  min(len(actual), len(expected)))
                    raise AssertionError(f"case batch starting at {compared}, -O{level}, byte {offset}: "
                                         f"Python={actual[offset:offset+8].hex()} "
                                         f"NASM={expected[offset:offset+8].hex()}")
                compared += len(batch)
    return compared


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=1200)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.batch_size)} cases")
