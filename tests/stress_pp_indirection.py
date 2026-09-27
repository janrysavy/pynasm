"""Compare NASM 3.02 preprocessor macro indirection in 8086 binaries."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define X 7\ndb %[X]",
    "%define X 7\n%define Y %[X]\n%undef X\ndb Y",
    "%define X 7\n%xdefine Y %[X]\n%undef X\ndb Y",
    "%define N 16\n%define Foo16 7\ndb Foo%[N]",
    "%define N 16\n%define Foo16 7\ndb %[Foo%[N]]",
    "%define Q 9\n%macro M 1\ndb %[%1]\n%endmacro\nM Q",
    "%define Q 9\n%macro M 1\ndb %[%1+1]\n%endmacro\nM Q",
    "%define M 5\ndb '%[M]'",
    "%define M 5\ndb %[M+1]",
    "%define A B\n%define B 4\ndb %[A]",
    "%define A 3\n%define B 4\ndb %[A],%[B]",
    "%define N 16\n%define Foo16 7\n%define X Foo%[N]\ndb X",
    "%define N 16\n%define Foo16 7\n%xdefine X Foo%[N]\ndb X",
    "%define N 16\n%define Foo16 7\n%define Foo%[N] 8\ndb Foo16",
    "%define N 16\n%define Foo16 7\n%ifdef Foo%[N]\ndb 1\n%endif",
    "%define N 16\n%define Foo16 7\n%ifdef %[Foo%[N]]\ndb 1\n%endif",
    "%define X 7\ndb 1 ; %[Missing",
    "%define N 16\n%macro M16 0\ndb 1\n%endmacro\nM%[N]",
    "%define N 16\n%macro M%[N] 0\ndb 1\n%endmacro\nM16",
    "%define N 16\n%macro M16 0\ndb 1\n%endmacro\n%ifmacro M%[N] 0\ndb 2\n%endif",
    "%define N 16\n%macro M16 0\ndb 1\n%endmacro\n%unmacro M%[N] 0\n"
    "%ifmacro M16 0\ndb 2\n%else\ndb 3\n%endif",
    "%define N 16\n%define F%[N](x) x\ndb F16(7)",
    "%define N 16\n%define F16(x) x\ndb F%[N](7)",
    "%define X 7\ndb 1 ; %[X]",
    "%define N 16\n%define Foo16 7\n%macro M 0\ndb %[Foo%[N]]\n%endmacro\nM",
    "%define N 16\n%define Foo16 7\n%undef Foo%[N]\n"
    "%ifdef Foo16\ndb 1\n%else\ndb 2\n%endif",
    "%define N 16\n%assign A%[N] 7\ndb A16",
    "%define N 16\n%defstr A%[N] hello\n%strlen L A16\ndb L",
    "%define N 16\n%define A16 7\n%defalias B%[N] A16\ndb B16",
    "%define N 16\n%define A16 7\n%defalias B16 A16\n%undefalias B%[N]\n"
    "%ifdefalias B16\ndb 1\n%else\ndb 2\n%endif",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "indirection.asm"
            output_file = Path(directory) / "indirection.bin"
            input_file.write_text(source, encoding="ascii")
            try:
                reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                            "-o", str(output_file), str(input_file)],
                                           capture_output=True, text=True, timeout=5)
            except subprocess.TimeoutExpired:
                return f"NASM timeout: {snippet!r} -O{level}"
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
