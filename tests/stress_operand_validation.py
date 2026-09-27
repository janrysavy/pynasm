"""Compare mixed valid/invalid 8086 operands with pinned NASM 3.02.

This optional live-NASM runner checks both acceptance and exact bytes for a
fixed-seed sample of size, branch, register, and qualifier combinations.
"""

import argparse
import concurrent.futures
import random
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


UNARY = ("push", "pop", "inc", "dec", "not", "neg", "mul", "imul", "div",
         "idiv", "jmp", "call", "int", "aad", "aam", "ret", "retf", "retn",
         "jo", "jnz", "loop", "jcxz")
BINARY = ("mov", "add", "adc", "sub", "sbb", "cmp", "or", "and", "xor",
          "test", "xchg", "lea", "lds", "les", "in", "out", "rol", "ror",
          "shl", "shr", "sar")
OPERANDS = (
    "al", "ah", "ax", "bx", "cx", "dx", "sp", "si", "cs", "ds", "es", "ss",
    "[bx]", "[bp+si+127]", "[0x1234]", "byte [bx]", "word [bx]",
    "dword [bx]", "qword [bx]", "far [bx]", "near [bx]", "short [bx]",
    "strict [bx]", "far ax", "far ds", "near ax", "short ax", "strict ax",
    "0", "1", "2", "127", "128", "255", "256", "-1", "byte 1", "word 1",
    "far 1:2", "short 1", "near 1", "strict 1",
)


def cases():
    rng = random.Random(98039)
    for mnemonic in UNARY:
        for _ in range(80):
            yield f"{mnemonic} {rng.choice(OPERANDS)}"
    for mnemonic in BINARY:
        for _ in range(100):
            first, second = rng.choices(OPERANDS, k=2)
            yield f"{mnemonic} {first},{second}"


def run(nasm: Path, workers: int = 8, levels: tuple[int, ...] = (0, 1, 9)) -> int:
    samples = list(cases())

    def compare(work):
        level, index, case = work
        source = "cpu 8086\n" + case + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "case.asm"
            output_file = Path(directory) / "case.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}", "-o",
                                        str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=3)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            actual_text = actual.hex() if actual is not None else "REJECT"
            expected_text = expected.hex() if expected is not None else "REJECT"
            return f"case {index} -O{level}: {case!r}: Python={actual_text} NASM={expected_text}"
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        work = ((level, index, case) for level in levels for index, case in enumerate(samples))
        differences = [message for message in executor.map(compare, work) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:50]))
    return len(samples) * len(levels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--levels", default="0,1,9", help="comma-separated NASM optimization levels")
    args = parser.parse_args()
    levels = tuple(int(level) for level in args.levels.split(","))
    print(f"compared {run(args.nasm, args.workers, levels)} cases")
