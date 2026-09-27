"""Compare NASM 3.02 single-line macro aliases under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define A 1\n%defalias B A\ndb B",
    "%defalias B A\n%define A 1\ndb B",
    "%define A 1\n%defalias B A\n%define A 2\ndb B",
    "%define A 1\n%defalias B A\n%define B 2\ndb A,B",
    "%define A 1\n%defalias B A\n%undef B\n"
    "%ifdef A\ndb 1\n%else\ndb 2\n%endif\n"
    "%ifdef B\ndb 3\n%else\ndb 4\n%endif",
    "%define A 1\n%defalias B A\n%undefalias B\n"
    "%ifdef A\ndb 1\n%endif\n%ifdef B\ndb 2\n%endif",
    "%define A 1\n%defalias B A\n%aliases off\n"
    "%aliases on\ndb B",
    "%idefine A 1\n%idefalias B A\ndb b",
    "%define A 1\n%defalias B A\n%defalias C B\ndb C",
    "%define A 1\n%defalias B A\n%defalias C B\n"
    "%define C 3\ndb A,B,C",
    "%define A 1\n%defalias B A\n%undefalias A\ndb B",
    "%undefalias UNKNOWN\ndb 1",
    "%defalias B UNKNOWN\n%ifdef B\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%undefalias A\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%idefine A 1\n%idefalias B A\n%define b 2\ndb A,b",
    "%idefine A 1\n%idefalias B A\n%undef b\n"
    "%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%defalias B A\n%ifdefalias B\ndb 1\n%else\ndb 2\n%endif",
    "%defalias B A\n%ifndefalias A\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%ifdefalias A\ndb 1\n%else\ndb 2\n%endif",
    "%idefalias B A\n%ifdefalias b\ndb 1\n%else\ndb 2\n%endif",
    "%defalias B A\n%undefalias B\n%ifdefalias B\ndb 1\n%else\ndb 2\n%endif",
    "%defalias B A\n%if 0\ndb 1\n%elifdefalias B\ndb 2\n%else\ndb 3\n%endif",
    "%define A 1\n%defalias B A\n%aliases off\ndb A",
    "%define A 1\n%defalias B A\n%aliases off\ndb B",
    "%define A(x) (x+1)\n%defalias B A\ndb B(2)",
    "%define A(x) (x+1)\n%defalias B A\n%undef B\n"
    "%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%defalias B A\n%ifidn B,A\ndb 1\n%else\ndb 2\n%endif",
    "%aliases off\ndb __BITS__",
    "%aliases off\ndb __?BITS?__",
    "%aliases off\n%aliases on\ndb __BITS__",
    "%aliases off\ndb __OUTPUT_FORMAT__",
    "%define A(x) (x+1)\n%defalias B(x) A\ndb B(2)",
    "%define A(x,y) (x+y)\n%defalias B(x,y) A\ndb B(2,3)",
    "%idefine A(x) (x+1)\n%idefalias B(x) A\ndb b(2)",
    "%define A(x) (x+1)\n%defalias B(x) A\n%undefalias B\n"
    "%ifdef A\ndb 1\n%endif",
)


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(itertools.product(SNIPPETS, (0, 1, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "aliases.asm"
            output_file = Path(directory) / "aliases.bin"
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
        differences = [message for message in executor.map(compare, generated) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
