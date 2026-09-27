"""Compare NASM 3.02 altreg package aliases under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


def cases():
    aliases = ([f"r{number}{suffix}" for number in range(8)
                for suffix in ("", "d", "w", "b", "l")] +
               [f"r{number}h" for number in range(4)] +
               [f"r{number}l" for number in range(8, 32)])
    for alias, level in itertools.product(aliases, (0, 9)):
        yield (f"%use altreg\n%ifdef {alias}\ndb 1\n%else\ndb 2\n%endif"), level
    for left, right, level in itertools.product(
            ("r0w", "r1w", "r2w", "r3w", "r4w", "r5w", "r6w", "r7w"),
            ("r0w", "r1w", "r7w"), (0, 9)):
        yield f"%use altreg\nmov {left},{right}", level
    for left, right, level in itertools.product(
            ("r0b", "r1b", "r2b", "r3b", "r0h", "r1h", "r2h", "r3h",
             "r0l", "r1l", "r4b", "r8l", "r0", "r0d", "R0W"),
            ("r0b", "r2h"), (0, 9)):
        yield f"%use altreg\nmov {left},{right}", level
    for source, level in itertools.product(
            ("%use altreg", "%use ALtReG\nmov R0W,R1W",
             "%use altreg\n%ifdef __?USE_ALTREG?__\ndb 1\n%endif",
             "%use altreg\n%ifdef __USE_ALTREG__\ndb 1\n%endif",
             "%use altreg\n%ifusing altreg\ndb 1\n%endif",
             "%use altreg\n%undef r0w\n%use altreg\n%ifdef r0w\ndb 1\n%endif",
             "%use altreg\n%undef r0w\n%ifdef r0w\ndb 1\n%endif",
             "%use altreg\nmov ax,r0w"), (0, 9)):
        yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file, output_file = Path(directory) / "altreg.asm", Path(directory) / "altreg.bin"
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
