"""Compare CPU 8086 INCBIN ranges and operand validation with NASM 3.02."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler, AssemblyError


def cases():
    for quote, level in itertools.product(("'", '"', '`'), (0, 9)):
        yield f"incbin {quote}sample.bin{quote}", level
    for offset, level in itertools.product(
            ("-2", "-1", "0", "1", "4", "5", "6", "0+2", "missing",
             "'1'", "'0'", '"0"'),
            (0, 9)):
        yield f'incbin "sample.bin",{offset}', level
    for offset, length, level in itertools.product(
            ("0", "1", "4", "5", "6", "-1"),
            ("-2", "-1", "0", "1", "2", "5", "6"), (0, 9)):
        yield f'incbin "sample.bin",{offset},{length}', level
    for snippet, level in itertools.product(
            ('incbin', 'incbin "sample.bin",',
             'incbin "sample.bin",1,',
             'incbin "sample.bin",1,2,3',
             'incbin "sample.bin",0,"2"',
             "incbin 'sample.bin',0,'2'",
             'incbin "sample.bin",0,"AB"',
             'incbin "sample.bin",0,missing',
             'incbin sample.bin', 'incbin 123',
             'incbin "absent.bin"',
             'times 2 incbin "sample.bin",1,2',
             'db 1\nincbin "sample.bin",2,2\ndb 2'), (0, 9)):
        yield snippet, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.bin").write_bytes(bytes(range(5)))
            input_file, output_file = root / "incbin.asm", root / "incbin.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       cwd=root, capture_output=True, text=True,
                                       timeout=5)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
            try:
                actual = Assembler(compatibility="nasm3", optimize=level,
                                   include_paths=[root]).assemble(
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
