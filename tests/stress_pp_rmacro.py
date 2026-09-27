"""Compare NASM 3.02 reserved multiline-macro aliases under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%rmacro M 0\ndb 1\n%endmacro\nM",
    "%irmacro M 0\ndb 2\n%endmacro\nm",
    "%rmacro M 1\ndb %1\n%endmacro\nM 3",
    "%irmacro M 1\ndb %1\n%endmacro\nm 4",
    "%rmacro M 1-2 5\ndb %1,%2\n%endmacro\nM 6",
    "%rmacro M 1+\ndb %1\n%endmacro\nM 7,8",
    "%rmacro M 0\ndb 9\n%endm\nM",
    "%rmacro M 0\ndb 10\n%endmacro\n%ifmacro M 0\ndb 1\n%endif\nM",
    "%irmacro M 0\ndb 11\n%endmacro\n%ifmacro m 0\ndb 1\n%endif\nm",
    "%imacro M 0\ndb 11\n%endmacro\n%ifmacro m 0\ndb 1\n%endif\nm",
    "%imacro M 0\ndb 11\n%endmacro\n%ifmacro M 0\ndb 1\n%endif\nm",
    "%irmacro M 0\ndb 11\n%endmacro\n%ifmacro M 0\ndb 1\n%endif\nm",
    "%imacro M 0\ndb 11\n%endmacro\n%ifdef m\ndb 1\n%else\ndb 2\n%endif\nm",
    "%imacro M 0\ndb 11\n%endmacro\n%ifdef M\ndb 1\n%else\ndb 2\n%endif\nm",
    "%rmacro M 0\ndb 12\n%endmacro\n%unmacro M 0\n%ifmacro M 0\ndb 1\n%else\ndb 2\n%endif",
    "%irmacro M 0\ndb 13\n%endmacro\n%unimacro m 0\n%ifmacro M 0\ndb 1\n%else\ndb 2\n%endif",
    "%rmacro M 0\n%rmacro N 0\ndb 14\n%endmacro\n%endmacro\nM\nN",
    "%rmacro M 0\ndb 1",
    "%irmacro M 0\ndb 1",
)


def run(nasm: Path, workers: int = 8) -> int:
    cases = list(itertools.product(SNIPPETS, (0, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "rmacro.asm"
            output_file = Path(directory) / "rmacro.bin"
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
