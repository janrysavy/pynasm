"""Compare NASM's bracketed DOLLARHEX switch and $-prefixed values."""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SOURCES = (
    "db $1a",
    "db $ff",
    "[dollarhex off]\ndb $1a",
    "[dollarhex off]\n$1a: db $1a-$",
    "[dollarhex off]\n%define $1a 7\ndb $1a",
    "[dollarhex off]\n%define $1a 1\n%if $1a\ndb 7\n%endif",
    "[dollarhex off]\n$1a equ 9\ndb $1a",
    "[dollarhex on]\ndb $1a",
    "[dollarhex off]\n[dollarhex on]\ndb $1a",
    "[dollarhex off]\n[dollarhex]\ndb $1a",
    "[dollarhex off]\n[dollarhex yes]\ndb $1a",
    "[dollarhex on]\n[dollarhex no]\n$12: db $12-$",
    "[dollarhex false]\n$12: db $12-$",
    "[dollarhex true]\ndb $12",
    "[dollarhex 0]\n$12: db $12-$",
    "[dollarhex 1]\ndb $12",
    "[dollarhex 2-2]\n$12: db $12-$",
    "[dollarhex 1+1]\ndb $12",
    "[DOLLARHEX OFF]\n$1a: db $1a-$",
    "dollarhex off\ndb $12",
    "[dollarhex off]\nmov al,$12\n$12: db 5",
    "[dollarhex off]\n$12: db 3\n[dollarhex on]\ndb $12",
)


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(index, level) for index in range(len(SOURCES)) for level in (0, 9)]

    def compare(case):
        index, level = case
        source = "cpu 8086\nbits 16\n" + SOURCES[index] + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "dollarhex.asm"
            output_file = Path(directory) / "dollarhex.bin"
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
            return (f"case {index} -O{level}: "
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
