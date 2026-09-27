"""Compare repetition and multiline-macro control flow with NASM 3.02."""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SOURCES = (
    "%rep 5\ndb 1\n%exitrep\ndb 2\n%endrep\ndb 3",
    "%assign N 0\n%rep 5\n%assign N N+1\n%if N=3\n%exitrep\n%endif\ndb N\n%endrep\ndb 9",
    "%rep 2\ndb 1\n%rep 3\ndb 2\n%exitrep\ndb 3\n%endrep\ndb 4\n%endrep",
    "%rep 0\n%exitrep\n%endrep\ndb 5",
    "%exitrep\ndb 1",
    "%macro M 0\n%rep 3\ndb 1\n%exitrep\n%endrep\ndb 2\n%endmacro\nM",
    "%macro M 0\ndb 1\n%exitmacro\ndb 2\n%endmacro\nM\ndb 3",
    "%macro M 0\n%rep 3\ndb 1\n%exitmacro\ndb 2\n%endrep\ndb 3\n%endmacro\nM\ndb 4",
    "%macro M 0\n%if 1\ndb 1\n%exitmacro\n%endif\ndb 2\n%endmacro\nM\ndb 3",
    "%macro M 0\n%rep 3\n%if 1\ndb 1\n%exitrep\n%endif\n%endrep\ndb 2\n%endmacro\nM",
    "%macro M 3\ndb %1,%2,%3\n%rotate 1\ndb %1,%2,%3\n%endmacro\nM 1,2,3",
    "%macro M 3\n%rotate -1\ndb %1,%2,%3\n%endmacro\nM 1,2,3",
    "%macro M 3\n%rotate 7\ndb %1,%2,%3\n%endmacro\nM 1,2,3",
    "%macro M 2\n%rep 2\ndb %1\n%rotate 1\n%endrep\n%endmacro\nM 4,5",
    "%macro M 0\n%rotate 1\ndb 1\n%endmacro\nM",
    "%exitmacro\ndb 1",
    "%macro M 0\n%if 0\n%exitmacro\n%endif\ndb 1\n%endmacro\nM",
    "%rep 2\n%if 0\n%exitrep\n%endif\ndb 1\n%endrep",
)


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(source, level) for source in SOURCES for level in (0, 9)]

    def compare(case):
        source, level = case
        source = "cpu 8086\nbits 16\n" + source + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "control.asm"
            output_file = Path(directory) / "control.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=10)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            return (f"case {SOURCES.index(case[0])} -O{level}: "
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
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
