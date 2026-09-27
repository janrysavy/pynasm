"""Compare deep but acyclic single-line macro chains with NASM 3.02."""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


LENGTHS = (1, 16, 32, 63, 64, 65, 96, 128, 192, 256, 384, 512,
           513, 768, 1024, 2048, 4096)


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(length, level) for length in LENGTHS for level in (0, 9)]

    def compare(case):
        length, level = case
        chain = [f"%define M{index} M{index + 1}" for index in range(length)]
        source = "cpu 8086\nbits 16\n" + "\n".join(chain) + f"\n%define M{length} 7\ndb M0\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "macro_depth.asm"
            output_file = Path(directory) / "macro_depth.bin"
            input_file.write_text(source, encoding="ascii")
            try:
                reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                            "-o", str(output_file), str(input_file)],
                                           capture_output=True, text=True, timeout=10)
            except subprocess.TimeoutExpired:
                return f"NASM timeout at length {length} -O{level}"
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            return (f"length {length} -O{level}: "
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
