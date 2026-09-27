"""Compare DEFAULT BND and explicit BND/NOBND under CPU 8086."""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SOURCES = (
    "[default abs]\nmov ax,[L]\nL: dw 7",
    "[default rel]\nmov ax,[L]\nL: dw 7",
    "[default bnd]\ncall L\nL: nop",
    "[default bnd]\njmp L\nL: nop",
    "[default bnd]\njmp short L\nL: nop",
    "[default bnd]\njmp near L\nL: nop",
    "[default bnd]\njz L\nL: nop",
    "[default bnd]\nret",
    "[default bnd]\nretn 4",
    "[default bnd]\nretf",
    "[default bnd]\niret",
    "[default bnd]\ncall ax",
    "[default bnd]\njmp ax",
    "[default bnd]\ncall word [bx]",
    "[default bnd]\njmp word [bx]",
    "[default bnd]\ncall far [bx]",
    "[default bnd]\njmp far [bx]",
    "[default bnd]\ncall 0:0",
    "[default bnd]\njmp 0:0",
    "[default bnd]\nnop",
    "[default bnd]\n[default nobnd]\ncall L\nL: nop",
    "[default bnd]\nnobnd call L\nL: nop",
    "[default bnd]\nnobnd ret",
    "[default bnd]\nnobnd jz L\nL: nop",
    "bnd call L\nL: nop",
    "bnd jmp L\nL: nop",
    "bnd jmp near L\nL: nop",
    "bnd jmp short L\nL: nop",
    "bnd jz L\nL: nop",
    "bnd ret",
    "nobnd ret",
    "[default bnd]\nrep call L\nL: nop",
    "[default bnd]\nrepne call L\nL: nop",
    "[default bnd]\nrepne jz L\nL: nop",
    "default bnd\ncall L\nL: nop",
    "[default rel,bnd]\ncall L\nL: nop",
    "[default bnd,rel]\ncall L\nL: nop",
    "[default bnd]\njmp L\ntimes 126 db 0\nL: nop",
    "[default bnd]\njmp L\ntimes 127 db 0\nL: nop",
    "[default bnd]\njz L\ntimes 126 db 0\nL: nop",
    "[default bnd]\njz L\ntimes 127 db 0\nL: nop",
    "[default bnd]\n[default nobnd]\n[default bnd]\nret",
    "[default bnd]\nnobnd nop",
    "bnd nop",
    "[default]\ndb 7",
    "[default ,]\ndb 7",
    "[default rel bnd]\nret",
    "[default fs:rel]\nmov ax,[L]\nL: dw 7",
    "[default gs:abs]\nmov ax,[L]\nL: dw 7",
    "[default bnd,nobnd]\nret",
    "[default nobnd,bnd]\nret",
    "[default invalid]\ndb 7",
    "[default bnd invalid]\ndb 7",
    "default bnd,nobnd\nret",
    "default bnd,rel\nret",
    "bnd\ndb 7",
    "nobnd\ndb 7",
    "[default bnd]\nretw",
    "[default bnd]\nretnw",
    "[default bnd]\nretfw",
    "[default bnd]\nloop L\nL: nop",
    "[default bnd]\njnz L\nL: nop",
    "[default bnd]\njmp dword L\nL: nop",
)


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(index, level) for index in range(len(SOURCES)) for level in (0, 1, 9)]

    def compare(case):
        index, level = case
        source = "cpu 8086\nbits 16\n" + SOURCES[index] + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "bnd.asm"
            output_file = Path(directory) / "bnd.bin"
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
