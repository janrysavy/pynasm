"""Differential matrix for NASM's 64-bit integer expression operators."""

import argparse
import subprocess
import tempfile
from pathlib import Path

from pynasm import assemble


VALUES = ("-3", "-1", "0", "1", "2", "3", "0x7fffffff", "0x80000000",
          "0xffffffff", "0x100000000", "0x7fffffffffffffff",
          "0x8000000000000000", "0xffffffffffffffff")
OPERATORS = ("+", "-", "*", "/", "//", "%", "%%", "<<", "<<<", ">>", ">>>",
             "&", "^", "|", "&&", "^^", "||", "=", "==", "!=", "<>",
             "<", "<=", ">", ">=", "<=>")


def cases():
    for operator in OPERATORS:
        for left in VALUES:
            for right in VALUES:
                if operator in ("/", "//", "%", "%%") and right == "0":
                    continue
                # NASM 3.02 stalls on signed INT64_MIN / -1 and its modulo.
                if (operator in ("//", "%%") and left == "0x8000000000000000"
                        and right in ("-1", "0xffffffffffffffff")):
                    continue
                if operator in ("<<", "<<<", ">>", ">>>") and right not in (
                        "-3", "-1", "0", "1", "2", "3"):
                    continue
                yield f"dq ({left}) {operator} ({right})"


def run(nasm: Path, batch_size: int = 100) -> int:
    instructions = list(cases())
    with tempfile.TemporaryDirectory() as directory:
        input_file = Path(directory) / "expressions.asm"
        output_file = Path(directory) / "expressions.bin"
        for start in range(0, len(instructions), batch_size):
            batch = instructions[start:start + batch_size]
            source = "cpu 8086\n" + "\n".join(batch) + "\n"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", "-O0", "-o",
                                        str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=5)
            if reference.returncode:
                raise RuntimeError(reference.stderr)
            actual = assemble(source, compatibility="nasm3")
            expected = output_file.read_bytes()
            if len(actual) != len(expected):
                raise AssertionError(f"batch {start}: {len(actual)} vs {len(expected)} bytes")
            for index, line in enumerate(batch):
                offset = index * 8
                if actual[offset:offset + 8] != expected[offset:offset + 8]:
                    raise AssertionError(f"case {start + index}: {line}: "
                                         f"Python={actual[offset:offset+8].hex()} "
                                         f"NASM={expected[offset:offset+8].hex()}")
    return len(instructions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    args = parser.parse_args()
    print(f"compared {run(args.nasm)} expressions")
