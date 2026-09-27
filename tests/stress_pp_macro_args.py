"""Compare NASM 3.02 multiline-macro argument grouping and empty tails."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%macro M 1\ndb %0\n%endmacro\nM 1",
    "%macro M 1\ndb %0\n%endmacro\nM 1,",
    "%macro M 1\ndb %0\n%endmacro\nM 1,,",
    "%macro M 2\ndb %0\n%endmacro\nM 1,",
    "%macro M 2\ndb %0\n%endmacro\nM 1,,",
    "%macro M 2\ndb %0\n%endmacro\nM ,1",
    "%macro M 2\ndb %0\n%endmacro\nM ,",
    "%macro M 1+\ndb %0\n%endmacro\nM 1,2,",
    "%pragma preproc sane_empty_expansion yes\n%macro M 1\ndb %0\n%endmacro\nM 1,",
    "%pragma preproc sane_empty_expansion yes\n%macro M 2\ndb %0\n%endmacro\nM 1,",
    "%macro M 1-2 9\ndb %0,%1,%2\n%endmacro\nM 1,",
    "%pragma preproc sane_empty_expansion yes\n%macro M 1-2 9\ndb %0,%1,%2\n%endmacro\nM 1,",
    "%macro M 1\ndb %1\n%endmacro\nM {7}",
    "%macro M 1\ndb %1\n%endmacro\nM {7,8}",
    "%macro M 1\ndb %1\n%endmacro\nM {7,{8}}",
    "%macro M 1\ndb %1\n%endmacro\nM {7}+1",
    "%macro M 2\ndb %0\n%endmacro\nM {7,8},9",
    "%macro M 2\ndb %0\n%endmacro\nM {7,8},",
    "%macro M 1\ndb %1\n%endmacro\nM {'A'}",
    "%macro M 1\ndb %1\n%endmacro\nM {{7}}",
    "%macro M 1-2 {7}\ndb %2\n%endmacro\nM 1",
    "%macro M 1-2 {7,8}\ndb %2\n%endmacro\nM 1",
    "%macro M 1-3 7,\ndb %0\n%endmacro\nM 1",
    "%pragma preproc sane_empty_expansion yes\n%macro M 1-3 7,\ndb %0\n%endmacro\nM 1",
    "%macro M 2\ndb %0\n%endmacro\nM (1,2)",
    "%macro M 2\ndb %0\n%endmacro\nM [1,2]",
    "%macro M 3\ndb %0\n%endmacro\nM (1,(2,3))",
    "%macro M 1-3 (7,8)\ndb %0\n%endmacro\nM 1",
    "%macro M 1-3 [7,8]\ndb %0\n%endmacro\nM 1",
    "%macro M 1-3 {7,8}\ndb %0\n%endmacro\nM 1",
    "%macro M 1-3 'a,b'\ndb %0\n%endmacro\nM 1",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "macro_args.asm"
            output_file = Path(directory) / "macro_args.bin"
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
