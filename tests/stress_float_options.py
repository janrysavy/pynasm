"""Compare NASM FLOAT rounding and denormal directives on 8086 data."""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SOURCES = (
    "[float near]\ndd 1.0000001",
    "[float down]\ndd 1.0000001",
    "[float up]\ndd 1.0000001",
    "[float zero]\ndd 1.0000001",
    "[float near]\ndd -1.0000001",
    "[float down]\ndd -1.0000001",
    "[float up]\ndd -1.0000001",
    "[float zero]\ndd -1.0000001",
    "[float daz]\ndd 1e-40",
    "[float daz]\ndd -1e-40",
    "[float daz]\n[float nodaz]\ndd 1e-40",
    "[float daz]\n[float default]\ndd 1e-40",
    "[float up]\n[float default]\ndd 1.0000001",
    "[float up]\ndd 0x1.000001p0",
    "[float down]\ndd -0x1.000001p0",
    "[float up]\ndq 1.0000000000000002",
    "[float down]\ndq 1.0000000000000002",
    "[float up]\ndt 1.0000000000000000001",
    "[float down]\ndt 1.0000000000000000001",
    "[float up]\ndo 1.0000000000000000000000000000000001",
    "[float down]\ndo 1.0000000000000000000000000000000001",
    "%use fp\n[float up]\ndd float32(1.0000001)",
    "%use fp\n[float down]\ndd float32(-1.0000001)",
    "[FLOAT UP]\ndd 1.0000001",
    "[float nonsense]\ndd 1.0",
    "float up\ndd 1.0",
    "float daz,up\ndd 1.0000001,1e-40",
    "float down,zero\n%ifidni __?FLOAT_ROUND?__,zero\ndb 7\n%endif",
    "float daz\n%ifidni __?FLOAT_DAZ?__,daz\ndb 8\n%endif",
    "float default\n%ifidni __?FLOAT?__,nodaz,near\ndb 9\n%endif",
    "[float up]\n%ifidni __?FLOAT_ROUND?__,near\ndb 10\n%endif",
    "[float down]\ndd -1e-40",
    "[float down]\ndd -1e-50",
    "[float up]\ndd 1e-40",
    "[float up]\ndd 1e-50",
    "[float up]\ndd 1.1e10",
    "[float up]\ndd 1.000000059604644775390625",
    "[float up]\ndw 1.0001",
)


def run(nasm: Path, workers: int = 4) -> int:
    cases = [(index, level) for index in range(len(SOURCES)) for level in (0, 9)]

    def compare(case):
        index, level = case
        source = "cpu 8086\nbits 16\n" + SOURCES[index] + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "float.asm"
            output_file = Path(directory) / "float.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=10)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            return (f"case {index} -O{level}: "
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
