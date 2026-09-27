"""Large, opt-in 8086 encoding differential from NASM 3.02 insns.dat.

The table selects the 8086 arithmetic/data-move instruction families. This
generator expands their register/memory forms over displacement and segment
boundaries; it does not claim to enumerate every table entry.
"""

import argparse
import hashlib
import itertools
import re
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler


INSNS_SHA256 = "34c98c66fb85e08655823f1fb8e267ca61af5b172e97f2220efedc7ac8f81571"
REGISTERS = ("al cl dl bl ah ch dh bh ax cx dx bx sp bp si di").split()
BASES = ("bx", "bp", "si", "di", "bx+si", "bx+di", "bp+si", "bp+di")
DISPLACEMENTS = ("-129", "-128", "-127", "-1", "0", "1", "127", "128", "129")
SEGMENTS = ("", "es:", "cs:", "ss:", "ds:")


def selected_mnemonics(table: bytes) -> tuple[str, ...]:
    if hashlib.sha256(table).hexdigest() != INSNS_SHA256:
        raise ValueError("insns.dat differs from the pinned NASM 3.02 revision")
    source = table.decode("ascii")
    arithmetic = next(line for line in source.splitlines() if line.startswith("$arith"))
    names = [name.lower() for name in re.findall(r"\b[A-Z]{2,}\b", arithmetic)]
    for name in ("MOV", "TEST", "XCHG"):
        if not re.search(rf"(?m)^\$bwdq {name}\s+.*\b8086\b", source):
            raise ValueError(f"missing 8086 {name} row")
        names.append(name.lower())
    return tuple(dict.fromkeys(names))


def cases(mnemonics: tuple[str, ...]):
    for register, base, displacement, segment, mnemonic in itertools.product(
            REGISTERS, BASES, DISPLACEMENTS, SEGMENTS, mnemonics):
        address = f"[{segment}{base}+{displacement}]"
        yield f"{mnemonic} {register},{address}"
        yield f"{mnemonic} {address},{register}"


def run(insns: Path, nasm: Path, count: int, batch_size: int,
        cpu: str = "8086") -> int:
    names = selected_mnemonics(insns.read_bytes())
    generated = itertools.islice(cases(names), count)
    compared = 0
    with tempfile.TemporaryDirectory() as directory:
        source_file = Path(directory) / "generated.asm"
        output_file = Path(directory) / "generated.bin"
        while batch := list(itertools.islice(generated, batch_size)):
            source = "cpu 8086\nbits 16\n" + "\n".join(batch) + "\n"
            source_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", "-O9", "-o",
                                        str(output_file), str(source_file)],
                                       capture_output=True, text=True)
            if reference.returncode:
                raise RuntimeError(reference.stderr)
            # NASM names the shared 8086/8088 ISA "8086"; our 8088 spelling
            # is an alias and must produce the same bytes.
            actual_source = source.replace("cpu 8086\n", f"cpu {cpu}\n", 1)
            actual = Assembler(optimize=9, compatibility="nasm3").assemble(actual_source)
            expected = output_file.read_bytes()
            if actual != expected:
                offset = next((i for i, pair in enumerate(zip(actual, expected))
                               if pair[0] != pair[1]), min(len(actual), len(expected)))
                raise AssertionError(f"batch after case {compared}: byte {offset}: "
                                     f"Python={actual[offset:offset+8].hex()} "
                                     f"NASM={expected[offset:offset+8].hex()}; "
                                     f"source retained only in temporary directory")
            compared += len(batch)
    return compared


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insns", required=True, type=Path)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=2_500)
    parser.add_argument("--cpu", choices=("8086", "8088"), default="8086")
    args = parser.parse_args()
    print(f"compared {run(args.insns, args.nasm, args.count, args.batch_size, args.cpu)} cases")
