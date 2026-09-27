"""Compare NASM 3.02 %pragma handling in 8086 flat binaries."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%pragma\ndb 1",
    "%pragma bluttan blej\ndb 1",
    "%pragma 'quoted namespace'\ndb 1",
    "%pragma preproc\ndb 1",
    "%pragma preproc tjo fidelittan\ndb 1",
    "%pragma preproc sane_empty_expansion yes\ndb 1",
    "%pragma preproc sane_empty_expansion no\ndb 1",
    "%pragma dbg tjo fidelittan output\ndb 1",
    "%pragma asm foobar\ndb 1",
    "%define PR asm foobar\n%pragma PR\ndb 1",
    "%define PR preproc\n%pragma PR sane_empty_expansion yes\ndb 1",
    "%pragma preproc sane_empty_expansion 1\ndb 1",
    "%pragma preproc sane_empty_expansion 0\ndb 1",
    "%macro M 1\ndb %0\n%endmacro\nM ",
    "%pragma preproc sane_empty_expansion yes\n%macro M 1\ndb %0\n%endmacro\nM ",
    "%macro M 1\ndb %0\n%endmacro\nM",
    "%pragma preproc sane_empty_expansion yes\n%macro M 1\ndb %0\n%endmacro\nM",
    "%define E\n%macro M 1\ndb %0\n%endmacro\nM E",
    "%pragma preproc sane_empty_expansion yes\n%define E\n%macro M 1\ndb %0\n%endmacro\nM E",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "pragma.asm"
            output_file = Path(directory) / "pragma.bin"
            input_file.write_text(source, encoding="ascii")
            try:
                reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                            "-o", str(output_file), str(input_file)],
                                           capture_output=True, text=True, timeout=5)
            except subprocess.TimeoutExpired:
                return f"{snippet!r} -O{level}: NASM_TIMEOUT"
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            return (f"{snippet!r} -O{level}: "
                    f"Python={actual.hex() if actual is not None else 'REJECT'} "
                    f"NASM={expected.hex() if expected is not None else 'REJECT'} "
                    f"diagnostic={reference.stderr.strip()!r}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        differences = [message for message in executor.map(compare, cases) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences))
    return len(cases)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
