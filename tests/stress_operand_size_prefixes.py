"""Compare explicit operand-size prefixes with NASM 3.02 under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


PREFIXES = ("o16", "o32", "rep o32", "o32 rep", "a32 o32", "o32 a32",
            "o16 o32", "o32 o16", "o32 o32", "lock o32", "o32 lock")
INSTRUCTIONS = ("nop", "movsb", "stosw", "add ax,bx", "add ax,1",
                "mov ax,1", "mov word [bx],ax", "mov ax,[bx]",
                "mov ax,[0x1234]", "mov ax,[dword 0x1234]",
                "jmp $+2", "call $+3", "jo $+3", "loop $+2",
                "ret", "retf", "push ax", "pop ax", "inc ax",
                "xchg ax,bx", "fadd st1", "fadd dword [bx]")


def cases():
    for prefix, instruction, level in itertools.product(PREFIXES, INSTRUCTIONS, (0, 1, 9)):
        yield f"{prefix} {instruction}", level
    for source, level in itertools.product(
            ("o16", "o32", "o32 jmp word $+2", "o32 jmp dword $+2",
             "o16 jmp dword $+2", "o32 call word $+3",
             "o32 call dword $+3", "o16 call dword $+3",
             "o32 jo word $+3", "o32 jo dword $+3",
             "o16 jo dword $+3", "o32 loop word $+2",
             "o32 retw", "o32 retfw", "o32 mov eax,1",
             "o32 finit", "o32 fclex", "wait o32 finit",
             "o32 wait finit", "o32 pause"),
            (0, 1, 9)):
        yield source, level
    for mnemonic, padding, direction, level in itertools.product(
            ("jmp", "call", "jo", "loop"), (0, 125, 128),
            ("forward", "backward"), (0, 1, 9)):
        if direction == "forward":
            source = (f"o32 {mnemonic} target\ntimes {padding} db 0\n"
                      "target: nop")
        else:
            source = (f"target: nop\ntimes {padding} db 0\n"
                      f"o32 {mnemonic} target")
        yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        instruction, level = case
        source = "cpu 8086\n" + instruction + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "osize.asm", path / "osize.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=3)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            actual_text = actual.hex() if actual is not None else "REJECT"
            expected_text = expected.hex() if expected is not None else "REJECT"
            return (f"{instruction!r} -O{level}: "
                    f"Python={actual_text} NASM={expected_text}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        differences = [message for message in executor.map(compare, generated) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:80]))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
