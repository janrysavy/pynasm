"""Differential stress for NASM 3.02 flat-binary data directives under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


def cases():
    numbers = ("-65537", "-65536", "-32769", "-32768", "-257", "-256",
               "-129", "-128", "-1", "0", "1", "127", "128", "255",
               "256", "32767", "32768", "65535", "65536", "0xffffffff")
    for directive, number, level in itertools.product(
            ("db", "dw", "dd", "dq"), numbers, (0, 9)):
        yield f"{directive} {number}", level
    for directive, value, level in itertools.product(
            ("db", "dw", "dd", "dq"),
            ("'A'", "'AB'", "'ABC'", "'ABCDE'", "''", '"hello"',
             "`a\\n`", "'a',1,'bc'", "2 dup (3)", "2 dup ('ab')",
             "2 dup (1,2)", "0 dup (1)", "?", "1,", "", "1,,2",
             "1 dup (2 dup (3))", "2 dup (1,2 dup (3))",
             "2 dup (2 dup (3),4)", "2 dup ('dup (3)')"), (0, 9)):
        yield f"{directive} {value}", level
    for directive, value, level in itertools.product(
            ("db", "dw", "dd", "dq"),
            ("byte 0x1234", "word 0x1234", "dword 0x1234",
             "qword 0x1234", "word 'ABC'", "byte 2 dup (1)",
             "word 2 dup (1)", "1,word 2,3", "word (1,2)",
             "%(1,2)", "word %(1,2)", "tword 1.5",
             "oword 1.5", "tword 42", "oword 42",
             "tword 'ABC'", "oword 'ABC'", "yword 1.5",
             "zword 1.5", "yword 'ABC'", "zword 'ABC'"), (0, 9)):
        yield f"{directive} {value}", level
    for directive, value, level in itertools.product(
            ("dt", "do", "dy", "dz"),
            ("'ABC'", "1.5", "42", "byte 1", "word 42",
             "tword 1.5", "word 'ABC'", "%(1,2)",
             "2 dup ('x')"), (0, 9)):
        yield f"{directive} {value}", level
    for source, level in itertools.product(
            ("resb 0", "resb 1", "resw 3", "resd 2", "resq 1",
             "rest 1", "reso 1", "resy 1", "resz 1",
             "rest -1", "reso -1", "resy -1", "resz -1",
             "resb -1", "resb -2", "resw -1", "resd -1",
             "db 1\nresb -1\ndb 2", "db 1\nresw -1\ndb 2",
             "db 1\nresb -1\nend: dw end", "resw 1+2",
             "times 0 db 1", "times -1 db 1", "times 3 db 1,2",
             "times 2 dw 'abc'", "times 2 resb 2",
             "db 1\nalign 4", "db 1\nalign 4, db 0xff",
             "db 1\nalign 4, nop", "db 1\nalignb 4",
             "org 0x100\ndw $", "org 0x100\ndw $$",
             "start: db 1\ndw start", "start: db 1\ndw $-start"),
            (0, 9)):
        yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "data.asm"
            output_file = Path(directory) / "data.bin"
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
