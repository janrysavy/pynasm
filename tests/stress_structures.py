"""Compare NASM 3.02 standard structure macros under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "section .text\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
    "endstruc\ndb Pair_size,Pair.a,Pair.b",
    "section .text\nstruc Pair,4\n.a: resb 1\n.b: resw 1\n"
    "endstruc\ndb Pair_size,Pair.a,Pair.b",
    "section .data\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
    "endstruc\nistruc Pair\nat .a, db 7\nat .b, dw 0x1234\niend",
    "section .text\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
    "endstruc\nistruc Pair\nat .b, dw 0x1234\niend",
    "section .text\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
    "endstruc\nistruc Pair\nat Pair.a, db 7\niend",
    "section .text\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
    "endstruc\nistruc Pair\niend",
    "struc Pair\n.a: resb 1\nendstruc\ndb Pair_size",
    "section .text\nstruc Header\n.tag: resb 1\nalignb 4\n"
    ".word: resw 1\nendstruc\ndb Header_size,Header.word",
    "section .text\n%ifmacro struc 1-2\ndb 1\n%endif\n"
    "%ifmacro iend 0\ndb 2\n%endif",
    "section .data\nstruc Actor\n.x: resw 1\n.y: resw 1\n.name: resb 4\n"
    "endstruc\nplayer: istruc Actor\nat .x, dw 0x1234\n"
    "at .y, dw 0x5678\nat .name, db 'A',0\niend",
    "section .text\nstruc Triple\n.a: resb 1\n.b: resb 2\n"
    ".c: resb 3\nendstruc\nistruc Triple\nat .b, db 1,2\n"
    "at .c, db 3,4,5\niend",
    "section .text\nstruc Pair\n.a: resb 1\n.b: resb 1\n"
    "endstruc\nistruc Pair\nat .b\niend",
    "section .text\nstruc Pair\n.a: resb 1\n.b: resb 1\n"
    "endstruc\nistruc Pair\nat .b, db 1\nat .a, db 2\niend",
    "section .data\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
    "endstruc\nsection .text\nistruc Pair\nat .b, dw 7\niend\n"
    "section .data\ndb 8",
    "section .text\nstruc One\n.a: resb 1\nendstruc\n"
    "struc Two\n.a: resw 1\nendstruc\n"
    "db One_size,Two_size,One.a,Two.a",
    "section .text\nstruc Pair\n.a: resb 1\n"
    ".b: resb 1\nendstruc\n"
    "times 2 db Pair_size",
    "%unimacro struc 1-2\n%ifmacro struc 1-2\ndb 1\n"
    "%else\ndb 2\n%endif",
    "%unimacro struc 1-2\nstruc Pair\n.a: resb 1\nendstruc",
)


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(itertools.product(SNIPPETS, (0, 1, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "structures.asm"
            output_file = Path(directory) / "structures.bin"
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
