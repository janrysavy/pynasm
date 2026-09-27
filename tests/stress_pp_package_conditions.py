"""Compare NASM 3.02 package-availability preprocessor conditions."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


PACKAGES = ("fp", "ifunc", "altreg", "masm", "smartalign",
            "standard", "vtern", "unknown", "FP", "'fp'", '"IFUNC"',
            "`fp`", "fp extra", "", "1", "(fp)")
CONDITIONS = ("%ifusable", "%ifnusable", "%ifusing", "%ifnusing",
              "%elifusable", "%elifnusable", "%elifusing", "%elifnusing")
SETUPS = ("", "%use fp\n", "%use ifunc\n", "%use fp\n%use ifunc\n")


def cases():
    for setup, condition, package, level in itertools.product(
            SETUPS, CONDITIONS, PACKAGES, (0, 9)):
        branch = ("%if 0\ndb 3\n" if condition.startswith("%elif") else "")
        yield (setup + branch + f"{condition} {package}\ndb 1\n"
               "%else\ndb 2\n%endif"), level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file, output_file = Path(directory) / "package.asm", Path(directory) / "package.bin"
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
