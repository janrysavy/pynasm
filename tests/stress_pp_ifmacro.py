"""Compare NASM 3.02 %ifmacro condition parsing under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 0",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 1",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 2",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 4",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 0-1",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 3-5",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 4-*",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 2-1",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 4+",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 1-2+",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M 1 junk",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro M junk",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifnmacro M 2",
    "%macro M 1-3\ndb %1\n%endmacro\n%ifmacro",
    "%ifmacro",
    "%ifnmacro",
    "%ifmacro 123",
    "%ifmacro ABSENT 1",
    "%ifmacro ABSENT junk",
    "%ifmacro struc 1-2",
    "%ifmacro struc 3",
    "%define X M\n%macro M 1\ndb %1\n%endmacro\n%ifmacro X 1",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\ndb 1\n%else\ndb 2\n%endif\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "ifmacro.asm"
            output_file = Path(directory) / "ifmacro.bin"
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
