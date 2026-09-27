"""Differential byte/word/dword and short/near branch qualifiers.

This optional live-NASM matrix compares acceptance and exact bytes at three
optimization levels, including numeric and current-address targets.
"""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


MNEMONICS = ("jmp", "call", "jo", "jnz", "loop", "jcxz")
QUALIFIERS = ("", "byte ", "word ", "dword ", "short ", "near ",
              "byte short ", "word near ", "dword short ", "dword near ",
              "short dword ", "near dword ")
TARGETS = ("0", "1", "127", "128", "$+2", "$+3", "$+127", "$+128", "$+130")
LEVELS = (0, 1, 9)


def run(nasm: Path, workers: int = 8) -> int:
    combinations = list(itertools.product(MNEMONICS, QUALIFIERS, TARGETS, LEVELS))

    def compare(case):
        mnemonic, qualifier, target, level = case
        instruction = f"{mnemonic} {qualifier}{target}"
        source = "cpu 8086\nbits 16\n" + instruction + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "branch.asm", path / "branch.bin"
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
        differences = [message for message in executor.map(compare, combinations) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:50]))
    return len(combinations)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
