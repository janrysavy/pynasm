"""Compare flat-binary global directive acceptance with NASM 3.02."""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SOURCES = (
    "[list +]\ndb 7", "[list -]\ndb 7", "[list]\ndb 7",
    "[list +junk]\ndb 7", "list +\ndb 7",
    "[debug foo bar]\ndb 7", "[debug]\ndb 7", "[debug 7]\ndb 7",
    "debug foo\ndb 7",
    "[prefix X]\nfoo: dw foo", "[prefix]\nfoo: dw foo",
    "[suffix S]\nfoo: dw foo", "[postfix S]\nfoo: dw foo",
    "[gprefix X]\nfoo: dw foo", "[gsuffix S]\nfoo: dw foo",
    "[gpostfix S]\nfoo: dw foo", "[lprefix X]\nfoo: dw foo",
    "[lsuffix S]\nfoo: dw foo", "[lpostfix S]\nfoo: dw foo",
    "prefix X\nfoo: dw foo",
    "[static foo]\nfoo: db 7", "[static foo]\ndw foo",
    "[extern foo]\ndb 7", "[extern foo]\ndw foo",
    "[required foo]\ndb 7", "[required foo]\ndw foo",
    "[extern foo]\nfoo: db 7", "[required foo]\nfoo: db 7",
    "static foo\nfoo: db 7", "extern foo\ndb 7",
    "required foo\ndb 7", "extern foo,bar\ndb 7",
)


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(index, level) for index in range(len(SOURCES)) for level in (0, 9)]

    def compare(case):
        index, level = case
        source = "cpu 8086\nbits 16\n" + SOURCES[index] + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "directive.asm"
            output_file = Path(directory) / "directive.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=10)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            return (f"case {index} -O{level}: "
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
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
