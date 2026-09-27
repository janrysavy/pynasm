"""Differential 8086 forms outside the large arithmetic/data-move matrix.

This is an optional live-NASM stress runner; the package has no NASM runtime
dependency. Generated instructions are assembled in batches, and a mismatch is
bisected to report the individual source instruction.
"""

import argparse
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler, AssemblyError
from pynasm.isa8086 import JCC


REG8 = "al cl dl bl ah ch dh bh".split()
REG16 = "ax cx dx bx sp bp si di".split()
SEGMENTS = "es cs ss ds".split()
ADDRESSES = ("[bx]", "[bp]", "[si]", "[di]", "[bx+si]", "[bx+di]",
             "[bp+si]", "[bp+di]", "[0x1234]", "[es:bx+127]",
             "[ss:bp-128]", "[ds:si+128]")


def cases():
    for mnemonic in ("push", "pop"):
        for operand in itertools.chain(REG16, SEGMENTS, (f"word {a}" for a in ADDRESSES)):
            yield f"{mnemonic} {operand}"
    for mnemonic in ("inc", "dec", "not", "neg", "mul", "imul", "div", "idiv"):
        for operand in itertools.chain(REG8, REG16,
                                       (f"{size} {a}" for size in ("byte", "word") for a in ADDRESSES)):
            yield f"{mnemonic} {operand}"
    for mnemonic in ("rol", "ror", "rcl", "rcr", "shl", "sal", "shr", "sar"):
        for operand in itertools.chain(REG8, REG16,
                                       (f"{size} {a}" for size in ("byte", "word") for a in ADDRESSES)):
            for amount in ("1", "cl", "cx"):
                yield f"{mnemonic} {operand},{amount}"
    for segment, register in itertools.product(SEGMENTS, REG16):
        yield f"mov {segment},{register}"
        yield f"mov {register},{segment}"
    for segment, address in itertools.product(SEGMENTS, ADDRESSES):
        yield f"mov {segment},{address}"
        yield f"mov {address},{segment}"
    for mnemonic, register, address in itertools.product(("lea", "lds", "les"), REG16, ADDRESSES):
        yield f"{mnemonic} {register},{address}"
    for register, address, size in itertools.product(REG16, ADDRESSES,
                                                     ("byte", "dword", "qword", "tword")):
        yield f"lea {register},{size} {address}"
    for mnemonic, operand in itertools.product(("jmp", "call"),
                                                itertools.chain(REG16,
                                                                (f"far {register}" for register in REG16),
                                                                (f"word {a}" for a in ADDRESSES),
                                                                (f"far {a}" for a in ADDRESSES),
                                                                ("far 0x1234:0x5678",))):
        yield f"{mnemonic} {operand}"
    for register, port in itertools.product(("al", "ax"), ("0", "1", "127", "128", "255", "dx")):
        yield f"in {register},{port}"
        yield f"out {port},{register}"
    for mnemonic in ("aad", "aam", "int"):
        for value in ("0", "1", "127", "128", "255"):
            yield f"{mnemonic} {value}"
    for mnemonic in ("ret", "retn", "retf", "retw", "retnw", "retfw"):
        yield mnemonic
        for value in ("0", "1", "127", "128", "255", "256", "65535"):
            yield f"{mnemonic} {value}"
    for mnemonic in sorted(JCC):
        loop_family = JCC[mnemonic] >= 0xE0
        displacements = (-128, -127, -2, -1, 0, 1, 126, 127) if loop_family else (
            -130, -129, -128, -127, -2, -1, 0, 1, 126, 127, 128, 129)
        for displacement in displacements:
            yield f"{mnemonic} $+{displacement + 2}"
    for index, mnemonic in enumerate(sorted(JCC)):
        loop_family = JCC[mnemonic] >= 0xE0
        paddings = (0, 125, 126, 127) if loop_family else (0, 125, 126, 127, 128, 129)
        for padding in paddings:
            label = f"branch_{index}_{padding}"
            yield f"{mnemonic} {label}\ntimes {padding} db 0\n{label}: nop"
            if not loop_family or padding <= 125:
                yield f"{label}_back: nop\ntimes {padding} db 0\n{mnemonic} {label}_back"


def run(nasm: Path, batch_size: int = 300, cpu: str = "8086") -> int:
    all_cases = list(cases())
    with tempfile.TemporaryDirectory() as directory:
        source_file = Path(directory) / "misc.asm"
        output_file = Path(directory) / "misc.bin"

        def compare(batch, level):
            source = "cpu 8086\nbits 16\n" + "\n".join(batch) + "\n"
            source_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}", "-o",
                                        str(output_file), str(source_file)],
                                       capture_output=True, text=True, timeout=10)
            if reference.returncode:
                if len(batch) > 1:
                    half = len(batch) // 2
                    compare(batch[:half], level)
                    compare(batch[half:], level)
                    raise AssertionError(f"NASM rejects combined batch of {len(batch)} cases -O{level}: "
                                         f"{batch[0]!r} ... {batch[-1]!r}: {reference.stderr}")
                raise AssertionError(f"NASM rejects {batch[0]!r}: {reference.stderr}")
            try:
                actual_source = source.replace("cpu 8086\n", f"cpu {cpu}\n", 1)
                actual = Assembler(optimize=level, compatibility="nasm3").assemble(actual_source)
            except AssemblyError as exc:
                if len(batch) > 1:
                    half = len(batch) // 2
                    compare(batch[:half], level)
                    compare(batch[half:], level)
                    raise AssertionError(f"Python rejects combined batch of {len(batch)} cases -O{level}: "
                                         f"{batch[0]!r} ... {batch[-1]!r}: {exc}") from exc
                raise AssertionError(f"Python rejects {batch[0]!r} -O{level}: {exc}") from exc
            expected = output_file.read_bytes()
            if actual != expected:
                if len(batch) > 1:
                    half = len(batch) // 2
                    compare(batch[:half], level)
                    compare(batch[half:], level)
                    raise AssertionError(f"combined batch differs for {len(batch)} cases -O{level}: "
                                         f"{batch[0]!r} ... {batch[-1]!r}")
                raise AssertionError(f"{batch[0]!r} -O{level}: Python={actual.hex()} NASM={expected.hex()}")

        for level in (0, 1, 9):
            for offset in range(0, len(all_cases), batch_size):
                compare(all_cases[offset:offset + batch_size], level)
    return len(all_cases) * 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--cpu", choices=("8086", "8088"), default="8086")
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.batch_size, args.cpu)} cases")
