"""Compare floating data across NASM widths and rounding modes."""

import argparse
import concurrent.futures
import random
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


def _generated_values() -> tuple[str, ...]:
    rng = random.Random(8086)
    values = []
    for index in range(84):
        digit_count = (1, 2, 10, 25, 52, 53, 70)[index % 7]
        digits = "".join(str(rng.randrange(10)) for _ in range(digit_count))
        digits = digits.lstrip("0") or "1"
        value = (digits[0] + "." + (digits[1:] or "0") + "e" +
                 str(rng.choice((-300, -100, -40, -5, 0, 5, 40, 100, 300))))
        values.append("-" + value if index % 3 == 0 else value)
    return tuple(values)


DECIMAL_VALUES = (
    "1.0000001", "-1.0000001", "1e-5", "1e-10", "1e-20", "1e-40",
    "1e-50", "1e50", "1.1e10", "1.000000059604644775390625",
    "1.000000178813934326171875", "1.0001", "0.1", "0.3", "0.5",
    "1.5", "2.5", "3.1415926535897932384626433832795028841971",
    "1e-100", "1e100", "1e-1000", "1e1000",
) + _generated_values()
RADIX_VALUES = (
    "0x1.000001p0", "0x1.000003p0", "0x1.0000001p0",
    "0x1.fffffffffffffp0", "0x1.1p-30", "0x1p-150", "0x1p100",
    "0b1.001p0", "0o1.234p0", "-0x1.000001p0", "-0x1.1p-30",
    "0x1.0p-200", "0x1.0p200",
)
VALUES = DECIMAL_VALUES + RADIX_VALUES
WIDTHS = {"db": 1, "dw": 2, "dd": 4, "dq": 8, "dt": 10, "do": 16}
MODES = ("near", "down", "up", "zero", "daz", "default")


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(mode, directive, width, level)
             for mode in MODES for directive, width in WIDTHS.items()
             for level in (0, 9)]

    def compare(case):
        mode, directive, width, level = case
        source = ("cpu 8086\nbits 16\n[float " + mode + "]\n" +
                  "\n".join(f"{directive} {value}" for value in VALUES) + "\n")
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "precision.asm"
            output_file = Path(directory) / "precision.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=10)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError as exc:
            return [f"{mode} {directive} -O{level}: Python rejected: {exc}"]
        if expected is None:
            return [f"{mode} {directive} -O{level}: NASM rejected: "
                    f"{reference.stderr.strip()}"]
        if len(actual) != len(expected):
            return [f"{mode} {directive} -O{level}: output lengths "
                    f"Python={len(actual)} NASM={len(expected)}"]
        return [f"{mode} {directive} {value} -O{level}: "
                f"Python={actual[index * width:(index + 1) * width].hex()} "
                f"NASM={expected[index * width:(index + 1) * width].hex()}"
                for index, value in enumerate(VALUES)
                if actual[index * width:(index + 1) * width] !=
                   expected[index * width:(index + 1) * width]]

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        differences = [message for batch in executor.map(compare, cases) for message in batch]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences))
    return len(cases) * len(VALUES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
