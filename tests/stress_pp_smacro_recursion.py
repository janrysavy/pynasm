"""Compare NASM 3.02 recursive single-line macro expansion."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define A A+1\n%defstr S A\ndb S",
    "%define A A+1\n%defstr S A,A\ndb S",
    "%define F(x) 1+F(x)\n%defstr S F(3)\ndb S",
    "%define A B\n%define B A\n%defstr S A\ndb S",
    "%define F(x) G(x)\n%define G(x) F(x)\n%defstr S F(3)\ndb S",
    "%idefine F(x) f(x)+1\n%defstr S F(3)\ndb S",
    "%define F(x) x\n%defstr S F(F(1))\ndb S",
    "%define A 5\n%define B A+1\n%defstr S B\ndb S",
    "%define F(x) x+F(x)\n%defstr S F(2),F(3)\ndb S",
    "%define F(x) x\n%define A F(A)\n%defstr S A\ndb S",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "smacro_recursion.asm"
            output_file = Path(directory) / "smacro_recursion.bin"
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
