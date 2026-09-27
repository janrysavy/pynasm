"""Compare NASM 3.02 legacy %ifdifi conditional behavior under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%ifdifi A,a\ndb 1\n%else\ndb 2\n%endif",
    "%ifdifi 'A','a'\ndb 1\n%else\ndb 2\n%endif",
    "%ifdifi\ndb 1\n%else\ndb 2\n%endif",
    "%ifdifi 1,1\ndb 1\n%else\ndb 2\n%endif",
    "%ifndifi A,a\ndb 1\n%else\ndb 2\n%endif",
    "%ifndifi\ndb 1\n%else\ndb 2\n%endif",
    "%if 0\ndb 1\n%elifdifi A,a\ndb 2\n%else\ndb 3\n%endif",
    "%if 0\ndb 1\n%elifndifi A,a\ndb 2\n%else\ndb 3\n%endif",
    "%if 1\ndb 1\n%elifdifi A,a\ndb 2\n%endif",
    "%if 1\ndb 1\n%elifndifi A,a\ndb 2\n%endif",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "difi.asm"
            output_file = Path(directory) / "difi.bin"
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
