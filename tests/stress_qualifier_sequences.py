"""Compare combined operand size and distance qualifiers with NASM 3.02."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


QUALIFIERS = (
    "byte", "word", "dword", "short", "near", "far", "strict",
    "byte word", "word byte", "byte byte", "word word",
    "dword word", "word dword", "strict byte word", "word strict byte",
    "short near", "near short", "short far", "far short", "near far",
    "far near", "strict strict", "strict near", "near strict",
)
TEMPLATES = (
    "mov ax,{q} 1", "mov {q} [bx],1", "mov {q} [bx],ax",
    "add ax,{q} 1", "add {q} [bx],1", "add {q} [bx],ax",
    "jmp {q} $+3", "call {q} $+3", "jo {q} $+3",
    "push {q} [bx]", "ret {q} 2", "lea ax,{q} [bx]",
)


def cases():
    for qualifier, template, level in itertools.product(QUALIFIERS, TEMPLATES, (0, 1, 9)):
        yield template.format(q=qualifier), level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        instruction, level = case
        source = "cpu 8086\n" + instruction + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "qualifier.asm", path / "qualifier.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=3)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            actual_text = actual.hex() if actual is not None else "REJECT"
            expected_text = expected.hex() if expected is not None else "REJECT"
            return (f"{instruction!r} -O{level}: "
                    f"Python={actual_text} NASM={expected_text}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        differences = [message for message in executor.map(compare, generated) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:80]))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
