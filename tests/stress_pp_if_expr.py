"""Compare NASM 3.02 %if expression and trailing-token handling."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


CONDITIONS = (
    "%if 1", "%if 0", "%if 1 garbage", "%if 0 garbage",
    "%if 1,2", "%if 1 : 2", "%if 1)", "%if (1) garbage",
    "%if 1 (2)", "%if 1 @", "%if 1 +", "%if 1 + garbage",
    "%if 1 ? 2 : 3 junk", "%if 0 ? 2 : 3 junk",
    "%if 2*3 trailing", "%if (1+2)*3 trailing",
    "%if 1 < 2 trailing", "%if ~0 trailing",
    "%if 0\n%elif 1 trailing", "%if 0\n%elif 0 trailing",
    "%ifn 0", "%ifn 1", "%ifn 0 trailing",
    "%if 0\n%elifn 0", "%if 0\n%elifn 1",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(CONDITIONS, (0, 9)))

    def compare(case):
        condition, level = case
        source = "cpu 8086\nbits 16\n" + condition + "\ndb 1\n%else\ndb 2\n%endif\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "if_expr.asm"
            output_file = Path(directory) / "if_expr.bin"
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
