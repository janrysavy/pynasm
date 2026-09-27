"""Compare NASM 3.02 greedy single-line macros and conditional commas."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1,2)",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1,2,3)",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1,2,3,4)",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1,2,3,4,5)",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1,2,{3,4})",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1,2,)",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F(1)",
    "%define F(a,b,c+) a + 66 %, b * 3 %, c\ndb F()",
    "%define F(x+) 1 %, x\ndb F()",
    "%define F(x+) 1 %, x\ndb F(2)",
    "%define F(x+) 1 %, x\ndb F(2,3)",
    "%idefine F(x+) 1 %, x\ndb f(2,3)",
    "%define F(a,b,c+) a,b,c\ndb F(1,2,{3,4},5)",
    "%define F(a+,b) a,b\ndb F(1,2)",
    "%define F(a,b,c+) a,b,c\ndb F(1,2,3)",
    "%define F(a,b,c+) a,b,c\ndb F(1,2,3,4)",
    "%define F(x) 1 %, x\ndb F()",
    "%define F(x) 1 %, x\ndb F(2)",
    "%define F(x,y) x %, y\ndb F(1,)",
    "%define F(x,y) x %, y\ndb F(1,2)",
    "%define F(x+) x\ndb F(1,2,3)",
    "%define E\n%define F(x) 1 %, x\ndb F(E)",
    "%define F(a,b) 7\ndb F([1,2])",
    "%define F(a,b) 7\ndb F([1,2],3)",
    "%define F(a,b) 7\ndb F((1,2))",
    "%define F(a,b) 7\ndb F({1,2})",
    "%define F(a,b) 7\ndb F({1,2},3)",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "greedy.asm"
            output_file = Path(directory) / "greedy.bin"
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
