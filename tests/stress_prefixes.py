"""Differential explicit-prefix ordering, branch lengths, and validation."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


PREFIXES = ("lock", "rep", "repe", "repne", "wait", "es", "cs", "ss", "ds",
            "lock rep", "rep lock", "repne lock", "es rep", "rep es",
            "lock es", "es lock")
INSTRUCTIONS = ("nop", "movsb", "stosw", "scasb", "add word [bx],ax",
                "add ax,bx", "inc word [bx]", "inc ax", "xchg word [bx],ax",
                "cmp ax,bx", "jmp $+2", "call $+3", "jo $+2", "jnz short $+2",
                "fadd st1", "hlt",
                "int 3", "mov ax,[bx]", "out dx,al", "jmp ax",
                "jmp far [bx]", "call far [bx]")
DUPLICATES = ("rep rep nop", "rep repe nop", "repne repnz nop",
              "rep repne nop", "es es nop", "es cs nop", "lock lock nop",
              "wait wait nop", "rep wait nop", "wait rep nop")
SEGMENT_CONFLICTS = ("es mov ax,[es:bx]", "es mov ax,[cs:bx]",
                     "cs mov ax,[es:bx]", "rep es mov ax,[es:bx]",
                     "rep es mov ax,[cs:bx]", "es mov ax,[cs:0x1234]",
                     "es fadd dword [cs:bx]", "es mov [es:bx],ax")


def cases():
    for prefix, instruction, level in itertools.product(PREFIXES, INSTRUCTIONS, (0, 9)):
        yield f"{prefix} {instruction}", level
    for source, level in itertools.product(DUPLICATES, (0, 9)):
        yield source, level
    for source, level in itertools.product(SEGMENT_CONFLICTS, (0, 9)):
        yield source, level
    for instruction, level in itertools.product(
            ("repne jo dword $+3", "repnz jo byte $+2",
             "repne jnz near $+3", "repne loop $+2", "repne jcxz $+2"),
            (0, 1, 9)):
        yield instruction, level
    for instruction, level in itertools.product(
            ("repne ret", "repne retw", "repne retn", "repne retnw",
             "repne retf", "repne retfw", "repne ret 2", "repnz ret",
             "repne jmp ax", "repne jmp far [bx]", "repne call ax",
             "repne call far [bx]", "repne jmp short $+2"), (0, 9)):
        yield instruction, level
    for prefix, mnemonic in (("rep", "jmp"), ("lock", "jmp"),
                             ("wait", "call"), ("es", "jo"),
                             ("rep lock", "jnz"), ("rep", "loop"),
                             ("repne", "jo"), ("repne", "jnz")):
        for padding, direction, level in itertools.product(
                (0, 125, 126, 127, 128, 129), ("forward", "backward"), (0, 1, 9)):
            if mnemonic == "loop" and (padding >= 128 or
                                       direction == "backward" and padding >= 125):
                continue
            if direction == "forward":
                source = (f"{prefix} {mnemonic} target\ntimes {padding} db 0\n"
                          "target: nop")
            else:
                source = (f"target: nop\ntimes {padding} db 0\n"
                          f"{prefix} {mnemonic} target")
            yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        instruction, level = case
        source = "cpu 8086\n" + instruction + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "prefix.asm", path / "prefix.bin"
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
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:50]))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
