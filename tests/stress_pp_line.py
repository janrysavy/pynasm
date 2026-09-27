"""Compare NASM 3.02 %line source-location handling under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler, AssemblyError


SNIPPETS = (
    "%line 100\ndb __LINE__",
    "%line 100\ndb __LINE__\ndb __LINE__",
    "%line 100+2\ndb __LINE__\ndb __LINE__",
    "%line 100-2\ndb __LINE__\ndb __LINE__",
    "%line 100+0\ndb __LINE__\ndb __LINE__",
    "%line 5 virtual.asm\ndb __FILE__",
    "%line 5 'virtual.asm'\ndb __FILE__",
    "%line 5 \"virtual file.asm\" 1 2\ndb __FILE__",
    "%line 5 virtual.asm\ndb __LINE__,0\ndb __FILE__",
    "%if 0\n%line 50\n%endif\ndb __LINE__",
    "%line 9\n%if __LINE__ = 10\ndb 1\n%else\ndb 2\n%endif",
    "%line 5\n%define L __LINE__\ndb L",
    "%line foo\ndb 1",
    "%line 10+foo\ndb 1",
    "%line\ndb 1",
    "%line 7\ndb __LINE__\n%line 40\ndb __LINE__",
    "%line 0\ndb __LINE__",
    "%line 0x20+0x2\ndb __LINE__",
    "%line 9 +2\ndb __LINE__\ndb __FILE__",
    "%line 9+ 2\ndb 1",
    "%line 9+2 virtual.asm\ndb __LINE__\ndb __FILE__",
    "# 20 \"gcc.c\"\ndb __LINE__\ndb __FILE__",
    "# 20 \"gcc.c\" 1 3\ndb __LINE__\ndb __FILE__",
    "%macro M 0\n%line 30\ndb __LINE__\n%endmacro\nM\ndb __LINE__",
    "%macro M 0\ndb __LINE__\n%endmacro\n%line 30\nM\ndb __LINE__",
    "%line 5 virtual.asm\n%include 'body.inc'\ndb __LINE__",
    "%rep 2\ndb __LINE__\n%endrep\ndb __LINE__",
    "%line 40\n%rep 2\ndb __LINE__\n%endrep\ndb __LINE__",
    "%rep 2\n%line 20\ndb __LINE__\n%endrep\ndb __LINE__",
    "%line 10 outer.asm\n%include 'bodyline.inc'\ndb __LINE__\ndb __FILE__",
    "%macro M 0\n%rep 2\ndb __LINE__\n%endrep\n%endmacro\nM",
    "# 20 \"gcc\\x2ec\"\ndb __FILE__",
    "%line 10h+2\ndb __LINE__",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "line.asm"
            output_file = Path(directory) / "line.bin"
            (Path(directory) / "body.inc").write_text("db 42\n", encoding="ascii")
            (Path(directory) / "bodyline.inc").write_text(
                '%line 20 inner.asm\ndb __LINE__\n', encoding="ascii")
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-I", str(Path(directory)) + "/",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=5)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
            try:
                actual = Assembler(include_paths=[directory], compatibility="nasm3",
                                   optimize=level).assemble(source, filename=str(input_file))
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
