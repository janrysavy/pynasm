"""Deterministic complete-program branch and alignment differential.

Each case is a small flat binary with several mutually interacting forward and
backward branches. Compare each whole program so a length change can affect
later branches and alignment, rather than testing isolated instructions.
"""

import argparse
import random
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler, AssemblyError


def programs(count: int, seed: int):
    rng = random.Random(seed)
    for number in range(count):
        blocks = rng.randint(8, 18)
        lines = ["cpu 8086", "bits 16", "org 0x100"]
        for index in range(blocks):
            lines.append(f"label_{index}:")
            for _ in range(rng.randint(1, 3)):
                destination = rng.randrange(blocks)
                mnemonic = rng.choice(("jmp", "jz", "jnz", "jc", "jnc", "call"))
                lines.append(f"{mnemonic} label_{destination}")
            lines.append(rng.choice(("nop", "inc ax", "mov bx,[si+127]",
                                     "add byte [es:di],7", "rep movsb")))
            if rng.randrange(4) == 0:
                lines.append(f"align {rng.choice((2, 4, 8, 16))}, db 0x90")
            lines.append(f"times {rng.choice((0, 1, 7, 31, 63, 120, 125, 126, 127, 128, 129))} db 0")
        lines.append("end_label: ret")
        yield number, "\n".join(lines) + "\n"


def run(nasm: Path, count: int = 100, seed: int = 8088,
        cpu: str = "8086") -> int:
    compared = 0
    with tempfile.TemporaryDirectory() as directory:
        source_file = Path(directory) / "program.asm"
        output_file = Path(directory) / "program.bin"
        for number, source in programs(count, seed):
            source_file.write_text(source, encoding="ascii")
            for level in (0, 1, 9):
                reference = subprocess.run(
                    [str(nasm), "-f", "bin", f"-O{level}", "-o",
                     str(output_file), str(source_file)],
                    capture_output=True, text=True, timeout=5)
                if reference.returncode:
                    raise RuntimeError(f"NASM rejects generated program {number} "
                                       f"-O{level}: {reference.stderr}\n{source}")
                expected = output_file.read_bytes()
                try:
                    actual_source = source.replace("cpu 8086\n", f"cpu {cpu}\n", 1)
                    actual = Assembler(optimize=level, compatibility="nasm3").assemble(actual_source)
                except AssemblyError:
                    actual = None
                if actual != expected:
                    offset = next((i for i, pair in enumerate(zip(actual or b"", expected))
                                   if pair[0] != pair[1]),
                                  min(len(actual or b""), len(expected)))
                    raise AssertionError(
                        f"program {number}, seed {seed}, -O{level}, byte {offset}: "
                        f"Python={None if actual is None else actual[offset:offset+8].hex()} "
                        f"NASM={expected[offset:offset+8].hex()}\n"
                        f"NASM diagnostic: {reference.stderr}\n{source}")
                compared += 1
    return compared


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=8088)
    parser.add_argument("--cpu", choices=("8086", "8088"), default="8086")
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.count, args.seed, args.cpu)} programs")
