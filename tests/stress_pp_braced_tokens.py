"""Compare NASM 3.02 braced preprocessor-token forms."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%define V71 9\n%macro M 1\ndb V%{1}1\n%endmacro\nM 7",
    "%macro M 1\nj%{+1} L\nj%{-1} L\nL:\n%endmacro\nM ne",
    "%macro M 1\ndb %{0},%{1}\n%endmacro\nM 7",
    "%imacro Foo 0\n%ifidn %{?},foo\ndb 1\n%endif\n"
    "%ifidn %{??},Foo\ndb 2\n%endif\n%endmacro\nfoo",
    "%macro M 0\n%{%lab}: db 1\njmp %{%lab}\n%endmacro\nM",
    "%macro M 0\n%{%lab}bar: db 1\njmp %{%lab}bar\n%endmacro\nM",
    "%macro M 0\n%{%lab}: db 1\n%endmacro\nM\nM",
    "%macro M 1\ndb '%{1}'\n%endmacro\nM 7",
    "%push C\n%define %$foo 5\ndb %{$foo}\n%pop",
    "%{define} A 7\ndb A",
    "db 5 %{} 2",
    "%macro M 0\n%{%%lab}: db 1\n%endmacro\nM",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "braced_tokens.asm"
            output_file = Path(directory) / "braced_tokens.bin"
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
