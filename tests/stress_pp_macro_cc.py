"""Compare NASM 3.02 multiline-macro condition-code parameters."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = tuple(
    f"%macro M 1\nj%+1 L\nj%-1 L\nL:\n%endmacro\nM {cc}"
    for cc in ("a", "ae", "b", "be", "c", "e", "g", "ge", "l", "le",
               "na", "nae", "nb", "nbe", "nc", "ne", "ng", "nge",
               "nl", "nle", "no", "np", "ns", "nz", "o", "p", "pe",
               "po", "s", "z")
) + (
    "%macro M 1\n%ifidn %+1,cxz\ndb 1\n%endif\n%endmacro\nM cxz",
    "%macro M 1\n%ifidn %+1,ecxz\ndb 1\n%endif\n%endmacro\nM ecxz",
    "%macro M 1\n%ifidn %+1,rcxz\ndb 1\n%endif\n%endmacro\nM rcxz",
    "%macro M 1\n%ifidn %-1,cxz\ndb 1\n%endif\n%endmacro\nM cxz",
    "%macro M 1\n%ifidn %-1,ecxz\ndb 1\n%endif\n%endmacro\nM ecxz",
    "%macro M 1\n%ifidn %-1,rcxz\ndb 1\n%endif\n%endmacro\nM rcxz",
    "%macro M 1\n%ifidn %+1,foo\ndb 1\n%endif\n%endmacro\nM foo",
    "%macro M 1\n%ifidn %+1,ne\ndb 1\n%endif\n%endmacro\nM ne + x",
    "%macro M 1\n%ifidn %+0,ne\ndb 1\n%endif\n%endmacro\nM ne",
    "%macro M 1\n%ifidn %+2,ne\ndb 1\n%endif\n%endmacro\nM ne",
    "%macro M 2\n%rotate 1\nj%+1 L\nj%-2 L\nL:\n%endmacro\nM e,ne",
    "%macro M 1\ndb '%+1', '%-1'\n%endmacro\nM ne",
    "%macro M 1\nj%+1 L\nL:\n%endmacro\nM NE",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "macro_cc.asm"
            output_file = Path(directory) / "macro_cc.bin"
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
