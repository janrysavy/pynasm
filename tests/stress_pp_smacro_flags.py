"""Compare NASM 3.02 single-line macro parameter flags."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define F(=x) x\ndb F(13+5)",
    "%define F(=x) x\ndb F(1+2*3)",
    "%define F(=x/x) x\ndb F(13+5)",
    "%define F(=x/h) x\ndb F(13+5)",
    "%define F(=x/b) x\ndb F(5)",
    "%define F(=x/u) x\ndb F(-1)",
    "%define F(=x/s) x\ndb F(-1)",
    "%define F(&x) x\ndb F(ABC)",
    "%define F(&x) x\ndb F('ABC')",
    "%define F(&&x) x\ndb F('ABC')",
    "%define F(&&x) x\ndb F(ABC)",
    "%define F(&x) x\ndb F(1+2)",
    "%define F(!&x) x\ndb F(  ABC  )",
    "%define F(&!x) x\ndb F(  ABC  )",
    "%define F(,x) x\ndb F(1,7)",
    "%define F(x,) x\ndb F(7,9)",
    "%define F() 7\ndb F()",
    "%define F() 7\ndb F(1)",
    "%define F() 7\ndb F(1,2)",
    "%define F(=x/z) x\ndb F(7)",
    "%define F(=x) x\ndb F(missing)",
    "%define F(=x) x\ndb F(2+3,4)",
    "%define F(=x/x) x\n%ifidn F(18),0x12\ndb 1\n%else\ndb 2\n%endif",
    "%define F(=x/X) x\n%ifidn F(171),0XAB\ndb 1\n%else\ndb 2\n%endif",
    "%define F(=x/h) x\n%ifidn F(18),0h12\ndb 1\n%else\ndb 2\n%endif",
    "%define F(=x/u) x\n%ifidn F(-1),18446744073709551615\ndb 1\n%else\ndb 2\n%endif",
    "%define A ABC\n%define F(&x) x\ndb F(A)",
    "%define A 'ABC'\n%define F(&&x) x\ndb F(A)",
    "%define F(!&x) x\ndb F({A,B})",
    "%define F(=x,&y) x,y\ndb F(2+3,Hi)",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "smacro_flags.asm"
            output_file = Path(directory) / "smacro_flags.bin"
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
