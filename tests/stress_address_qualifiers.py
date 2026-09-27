"""Compare displacement size qualifiers inside 8086 memory brackets."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


QUALIFIERS = ("byte", "word", "dword", "qword", "tword",
              "byte word", "word byte", "byte dword", "dword byte",
              "word dword", "dword word", "byte qword", "qword byte",
              "word qword", "qword word")
ADDRESSES = ("bx", "bp", "bx+0", "bx+1", "bx+127", "bx+128",
             "bx-129", "0x1234", "bx+si+5")
TEMPLATES = ("mov ax,[{q} {a}]", "mov [{q} {a}],ax", "lea ax,[{q} {a}]")


def cases():
    for qualifier, address, template, level in itertools.product(
            QUALIFIERS, ADDRESSES, TEMPLATES, (0, 1, 9)):
        yield template.format(q=qualifier, a=address), level
    for source, level in itertools.product(
            ("mov ax,[es:byte bx]", "mov ax,[byte es:bx]",
             "mov ax,[es:word bx+1]", "mov ax,[word es:bx+1]",
             "mov ax,[es:dword 0x1234]", "mov ax,[dword es:0x1234]",
             "es mov ax,[dword 0x1234]", "rep mov ax,[dword 0x1234]",
             "lock mov ax,[dword 0x1234]", "rep lock mov ax,[dword 0x1234]",
             "rep mov ax,[es:bx]", "rep fadd dword [es:bx]",
             "wait rep fadd dword [es:bx]",
             "mov ax,[a16 bx]", "mov ax,[a32 0x1234]",
             "mov ax,[abs 0x1234]", "mov ax,[rel 0x1234]",
             "mov ax,[nosplit bx]", "mov ax,[a32 bx]",
             "mov ax,[a16 0x1234]", "mov ax,[a32 byte 0x1234]",
             "mov ax,[byte a32 0x1234]", "mov ax,[a32 word 0x1234]",
             "mov ax,[word a32 0x1234]", "mov ax,[a16 dword 0x1234]",
             "mov ax,[dword a16 0x1234]", "mov ax,[a16 a32 0x1234]",
             "mov ax,[a32 a16 0x1234]", "mov ax,[rel bx]",
             "mov ax,[abs bx]", "mov ax,[nosplit bx+si]"),
            (0, 1, 9)):
        yield source, level
    for source, level in itertools.product(
            ("a16 mov ax,[bx]", "a32 mov ax,[0x1234]", "a32 mov ax,[bx]",
             "a16 mov ax,[dword 0x1234]", "a32 mov ax,[word 0x1234]",
             "a16 nop", "a32 nop", "a32 movsb", "a32 rep movsb",
             "rep a32 movsb", "a16 a32 nop", "a32 a32 nop",
             "a16", "a32", "a32 jmp $+2", "a32 jo $+3",
             "a32 call $+3", "a32 repne jo $+2",
             "a32 fadd dword [0x1234]", "a32 fadd dword [bx]"),
            (0, 1, 9)):
        yield source, level
    for source, level in itertools.product(
            ("a16 loop $+2", "a32 loop $+2", "a16 loope $+2",
             "a32 loope $+2", "a32 loopne $+2", "a32 jcxz $+2",
             "a32 jecxz $+2", "a32 loopw $+2",
             "a32 loopew $+2", "a32 loopzw $+2",
             "a32 loopnew $+2", "a32 loopnzw $+2",
             "a16 loopw $+2", "a16 jcxz $+2",
             "a32 loop $+2,cx", "a32 loop $+2,ecx",
             "a32 loopw $+2,cx", "a16 loop $+2,ecx",
             "loop $+2,ecx", "loop $+2,cx",
             "jcxz $+2,ecx", "jcxz $+2,cx", "jecxz $+2",
             "start: a32 loop start", "start: a32 jcxz start",
             "a32 jcxz missing", "a32 loopw missing",
             "a32 jcxz ax", "a32 loopw ax", "a32 jcxz [bx]",
             "a32 loopw [bx]", "a32 jcxz $+2,cx",
             "a32 loopw $+2,ax", "a32 loop $+2,ax"),
            (0, 1, 9)):
        yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        instruction, level = case
        source = "cpu 8086\n" + instruction + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "address.asm", path / "address.bin"
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
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:70]))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
