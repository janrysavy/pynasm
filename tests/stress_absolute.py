"""Compare NASM 3.02 ABSOLUTE-space behavior under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "absolute 0x20\na: resb 1\nb: resw 2\nsection .text\ndw a,b,$-$$",
    "db 0xaa\nabsolute 0x20\na: resb 1\nsection .text\ndw a",
    "section .data\ndb 1\nabsolute 10\nfield: resd 2\n__SECT__\ndw field",
    "absolute 0\na: resb 1\nabsolute 10\nb: resw 1\nsection .text\ndw a,b",
    "absolute 3\na: resb 2\nb equ $\nsection .text\ndw a,b",
    "absolute 0x20\nresb 1\ndb 1\nsection .text\ndb 2",
    "absolute 0x20\nmov ax,bx\nsection .text\ndb 2",
    "absolute 0x20\na: db 1\nsection .text\ndw a",
    "absolute 0x20\nalignb 8\na: resb 1\nsection .text\ndw a",
    "absolute 0x20\nalign 8\na: resb 1\nsection .text\ndw a",
    "[absolute 0x20]\na: resb 1\nsection .text\ndw a",
    "absolute 0x21\nalignb 8\na: resb 1\nsection .text\ndw a",
    "absolute 0x21\na equ $$\nb equ $\nsection .text\ndw a,b",
    "absolute 0x20\ntimes 3 resb 2\na: resb 1\nsection .text\ndw a",
    "section .data\ndb 1\n[absolute 0x20]\na: resb 1\n__SECT__\ndw a",
    "absolute 0x20\na: resb 1\nsection .text\nmov ax,[a]",
    "absolute 0x20\na: resb 1\nsection .text\njmp a",
    "absolute 0x20\nalign 8\na: resb 1\nsection .text\ndw a",
    "absolute 0x21\nalign 8\na: resb 1\nsection .text\ndw a",
    "absolute 0x21\ntimes 0 db 1\na: resb 1\nsection .text\ndw a",
    "absolute 0x21\ntimes 2 resw 1\na: resb 1\nsection .text\ndw a",
)


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(itertools.product(SNIPPETS, (0, 1, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "absolute.asm"
            output_file = Path(directory) / "absolute.bin"
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
        differences = [message for message in executor.map(compare, generated) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
