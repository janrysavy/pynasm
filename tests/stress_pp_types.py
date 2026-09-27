"""Compare NASM 3.02 preprocessor token-type conditions under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


CONDITIONS = (
    "%ifnum 1", "%ifnum +1", "%ifnum --1", "%ifnum - + 1",
    "%ifnum + - + 0xff", "%ifnum - A", "%ifnnum --1",
    "%ifid A", "%ifid A B", "%ifid $", "%ifid ..@foo",
    "%ifid 1", "%ifnid A", "%ifstr 'A'", "%ifstr `A`",
    "%ifstr A", "%ifnstr 'A'", "%iftoken A", "%iftoken +",
    "%iftoken 'A'", "%iftoken A B", "%ifntoken A B",
    "%ifempty", "%ifempty   ", "%ifempty A", "%ifnempty A",
    "%define X 1\n%ifnum X", "%define X 'a'\n%ifstr X",
    "%if 0\n%elifnum --1", "%if 0\n%eliftoken +",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(CONDITIONS, (0, 9)))

    def compare(case):
        condition, level = case
        source = "cpu 8086\nbits 16\n" + condition + "\ndb 1\n%else\ndb 2\n%endif\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "types.asm"
            output_file = Path(directory) / "types.bin"
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
            return (f"{condition!r} -O{level}: "
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
