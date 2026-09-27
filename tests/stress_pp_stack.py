"""Compare NASM 3.02 TASM-style stack directives under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%stacksize large\n%arg a:WORD\nmov ax,[a]",
    "%stacksize small\n%arg a:WORD\nmov ax,[a]",
    "%stacksize large\n%arg a:BYTE,b:WORD,c:DWORD\nmov al,[a]\nmov bx,[b]\nmov ax,[c]",
    "%stacksize large\n%arg a:WORD\n%arg b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%stacksize LARGE\n%arg a:WORD, b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%stacksize large\n%arg a:TWORD,b:WORD\nmov ax,[b]",
    "%stacksize large\n%arg a:OWORD,b:WORD\nmov ax,[b]",
    "%stacksize large\n%arg a:WORD,b:WORD extra\nmov ax,[a]\nmov bx,[b]",
    "%stacksize large\n%arg a :WORD\ndb 1",
    "%stacksize large\n%arg a: WORD\ndb 1",
    "%stacksize large\n%arg a:WORD, b:UNKNOWN\ndb 1",
    "%stacksize large\n%local a:WORD\nmov ax,[a]",
    "%push C\n%stacksize large\n%local a:WORD\nmov ax,[a]\n%pop",
    "%push C\n%stacksize small\n%local a:BYTE,b:DWORD\nmov al,[a]\nmov bx,[b]\n%pop",
    "%push C\n%stacksize large\n%local a:WORD\n%local b:WORD\n"
    "mov ax,[a]\nmov bx,[b]\n%pop",
    "%push C\n%stacksize large\n%local a:WORD\ndb %$localsize\n%pop",
    "%push C\n%assign %$localsize 0\n%stacksize large\n%local a:WORD\n"
    "mov ax,[a]\ndb %$localsize\n%pop",
    "%push C\n%assign %$localsize 0\n%stacksize small\n"
    "%local a:BYTE,b:DWORD\nmov al,[a]\nmov bx,[b]\ndb %$localsize\n%pop",
    "%push C\n%assign %$localsize 0\n%stacksize large\n"
    "%local a:WORD\n%local b:WORD\nmov ax,[a]\nmov bx,[b]\n"
    "db %$localsize\n%pop",
    "%push C\n%assign %$localsize 3\n%stacksize large\n"
    "%local a:WORD\ndb %$localsize\n%pop",
    "%stacksize small\n%local a:BYTE,b:DWORD\nmov al,[a]\nmov bx,[b]",
    "%stacksize large\n%local a:WORD\n%local b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%stacksize large\n%arg a:WORD\n%local b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%stacksize large\n%define SZ WORD\n%arg a:SZ\nmov ax,[a]",
    "%stacksize large\n%arg a:byte\nmov al,[a]",
    "%stacksize large\n%arg a:QWORD,b:WORD\nmov ax,[b]",
    "%stacksize large\n%local a:QWORD,b:WORD\nmov ax,[b]",
    "%stacksize large\n%local a:WORD = 2\nmov ax,[a]",
    "%stacksize large extra\n%arg a:WORD\nmov ax,[a]",
    "%stacksize large\n%arg a:WORD extra\nmov ax,[a]",
    "%stacksize large\n%arg a:WORD\n%stacksize small\n%arg b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%arg a:WORD\nmov ax,[a]",
    "%arg a:WORD,b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%arg a:WORD\n%arg b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%arg a:WORD\n%stacksize large\nmov ax,[a]",
    "%arg a:WORD\n%stacksize large\n%arg b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%stacksize flat\n%arg a:WORD\nmov ax,[a]",
    "%stacksize flat64\n%arg a:WORD\nmov ax,[a]",
    "%stacksize invalid\ndb 1",
    "%stacksize\ndb 1",
    "%stacksize large\n%arg a\ndb 1",
    "%stacksize large\n%arg a:UNKNOWN\ndb 1",
    "%stacksize large\n%local a\ndb 1",
    "%stacksize large\n%local a:UNKNOWN\ndb 1",
)

POST_8086_CASES = {
    "%arg a:WORD\nmov ax,[a]",
    "%arg a:WORD,b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%arg a:WORD\n%arg b:WORD\nmov ax,[a]\nmov bx,[b]",
    "%stacksize flat\n%arg a:WORD\nmov ax,[a]",
}


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "stack.asm"
            output_file = Path(directory) / "stack.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=5)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if snippet in POST_8086_CASES:
            if actual is not None or expected is None:
                return (f"{snippet!r} -O{level}: expected strict 8086 rejection; "
                        f"Python={actual.hex() if actual is not None else 'REJECT'} "
                        f"NASM={expected.hex() if expected is not None else 'REJECT'}")
            return None
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
