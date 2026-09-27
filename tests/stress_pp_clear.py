"""Compare NASM 3.02 %clear macro-table behavior under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define A 1\n%clear\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%clear define\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%clear def\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%clear smacro\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%clear all\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%clear nothing\ndb A",
    "%define A 1\n%clear macro\ndb A",
    "%define A 1\n%clear defalias\ndb A",
    "%define A 1\n%defalias B A\n%clear defalias\n%ifdef B\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%defalias B A\n%clear alldef\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
    "%macro M 0\ndb 1\n%endmacro\n%clear\n%ifmacro M 0\ndb 2\n%else\ndb 3\n%endif",
    "%macro M 0\ndb 1\n%endmacro\n%clear define\nM",
    "%macro M 0\ndb 1\n%endmacro\n%clear macro\n%ifmacro M 0\ndb 2\n%else\ndb 3\n%endif",
    "%clear badoption\ndb 1",
    "%clear none,ignore,-,--\ndb 1",
    "%clear define,macro\ndb 1",
    "%clear context define\ndb 1",
    "%define A 1\n%clear context define\ndb A",
    "%clear\ndb __?BITS?__",
    "%clear defalias\ndb __BITS__",
    "%clear\n%ifdef __?FILE?__\ndb 1\n%else\ndb 2\n%endif",
    "%clear\n%ifdef __?LINE?__\ndb 1\n%else\ndb 2\n%endif",
    "%undef __?LINE?__\n%ifdef __?LINE?__\ndb 1\n%else\ndb 2\n%endif",
    "%clear define\n%define __?LINE?__ 7\ndb __?LINE?__",
    "%define __?LINE?__ 7\ndb __?LINE?__",
    "%push C\n%define %$A 1\n%clear context define\n"
    "%ifdef %$A\ndb 1\n%else\ndb 2\n%endif\n%pop",
    "%define A 1\n%push C\n%define %$B 2\n%clear global define\n"
    "%ifdef A\ndb 1\n%else\ndb 2\n%endif\n"
    "%ifdef %$B\ndb 3\n%else\ndb 4\n%endif\n%pop",
    "%define A 1\n%push C\n%define %$B 2\n%clear context define\n"
    "%ifdef A\ndb 1\n%endif\n%ifdef %$B\ndb 2\n%endif\n%pop",
    "%macro M 0\ndb 1\n%endmacro\n%clear context macro\nM",
    "%clear macro\nstruc S\nresb 1\nendstruc",
    "%clear all\n%ifmacro struc 1\ndb 1\n%else\ndb 2\n%endif",
    "%define A 1\n%define O define\n%clear O\n%ifdef A\ndb 1\n%else\ndb 2\n%endif",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "clear.asm"
            output_file = Path(directory) / "clear.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=5)
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
