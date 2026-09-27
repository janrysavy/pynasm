"""Compare NASM 3.02 include spelling and search order for CPU 8086 sources."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler, AssemblyError


def cases():
    for source, level in itertools.product(
            ('%include "body.inc"', "%include 'body.inc'",
             '%include `body.inc`', '%include body.inc',
             '%include "sub/body.inc"', '%include "extra.inc"',
             '%include "nested.inc"', '%include "missing.inc"',
             '%include', '%include "body.inc" extra',
             '%define FILE "body.inc"\n%include FILE',
             '%include "body.inc"\n%include "body.inc"',
             '%pathsearch P "extra.inc"\n%include P',
             '%ipathsearch P "extra.inc"\n%include p',
             '%pathsearch P "missing.inc"\ndb P',
             '%pathsearch P extra.inc\ndb 1',
             '%require "body.inc"\n%require "body.inc"',
             '%include "body.inc"\n%require "body.inc"',
             '%require "body.inc"\n%include "body.inc"',
             '%require "missing.inc"',
             '%depend "missing.inc"\ndb 1',
             '%depend missing.inc\ndb 1',
             '%define FILE "body.inc"\n%require FILE'),
            (0, 9)):
        yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sub, extra = root / "sub", root / "extra"
            sub.mkdir()
            extra.mkdir()
            (root / "body.inc").write_text("db 65\n", encoding="ascii")
            (sub / "body.inc").write_text("db 66\n", encoding="ascii")
            (extra / "body.inc").write_text("db 67\n", encoding="ascii")
            (extra / "extra.inc").write_text("db 68\n", encoding="ascii")
            (root / "nested.inc").write_text('%include "body.inc"\n', encoding="ascii")
            input_file, output_file = sub / "source.asm", root / "include.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-I", str(extra) + "/", "-o", str(output_file),
                                        str(input_file)], cwd=root, capture_output=True,
                                       text=True, timeout=5)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
            try:
                actual = Assembler(compatibility="nasm3", optimize=level,
                                   include_paths=[root, extra]).assemble(
                                       source, filename=str(input_file))
            except AssemblyError:
                actual = None
        if actual != expected:
            actual_text = actual.hex() if actual is not None else "REJECT"
            expected_text = expected.hex() if expected is not None else "REJECT"
            return (f"{snippet!r} -O{level}: "
                    f"Python={actual_text} NASM={expected_text}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        differences = [message for message in executor.map(compare, generated) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:70]))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
