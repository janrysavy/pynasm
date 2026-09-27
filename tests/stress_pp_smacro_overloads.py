"""Compare NASM 3.02 single-line macro overload selection."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define F(x) x+1\n%define F(x,y) x+y\ndb F(2),F(2,3)",
    "%define F(x,y) x+y\n%define F(x) x+1\ndb F(2),F(2,3)",
    "%define F(x) 1\n%define F(y) 2\ndb F(9)",
    "%idefine Foo(x) 1\n%idefine fOO(x,y) 2\ndb foo(7),FOO(7,8)",
    "%define F(x+) 9\n%define F(x,y) 7\ndb F(1,2)",
    "%define F(x,y) 7\n%define F(x+) 9\ndb F(1,2)",
    "%define F(x+) 9\n%define F(x,y) 7\ndb F(1,2,3)",
    "%define F(x,y) 7\n%define F(x+) 9\ndb F(1,2,3)",
    "%define F(x) 1\n%define F(x,y) 2\n%undef F\n"
    "%ifdef F\ndb 3\n%else\ndb 4\n%endif",
    "%define F(x) 1\n%define F(x,y) 2\ndb F(1,2,3)",
    "%define F 1\n%define F(x) 2\ndb F(7)",
    "%define F(x) 2\n%define F 1\ndb F(7)",
    "%define F(x) 1\n%idefine F(x,y) 2\ndb F(7),f(7,8)",
    "%idefine F(x) 1\n%define F(x,y) 2\ndb f(7),F(7,8)",
    "%define F(x) 1\n%define F(x,y) 2\n%undef F\ndb F(1)",
    "%idefine Foo(x) %??\n%idefine fOO(x,y) %??\n"
    "%ifidn foo(7),Foo\ndb 1\n%endif\n"
    "%ifidn FOO(7,8),fOO\ndb 2\n%endif",
    "%define F 1\n%define f(x) 2\ndb F,f(3)",
    "%idefine F 1\n%define f(x) 2\ndb F,f(3)",
    "%define F(x) 1\n%idefine f 2\ndb F(3),f",
    "%idefine F(x) 1\n%define f 2\ndb F(3),f",
    "%idefine F 1\n%define F(x) 2\ndb F(3)",
    "%idefine F(x) 1\n%define F 2\ndb F",
    "%define F(x) 1\n%idefine f 2\ndb 9",
    "%define F 1\n%idefine f(x) 2\ndb 9",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "smacro_overloads.asm"
            output_file = Path(directory) / "smacro_overloads.bin"
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
