"""Compare NASM 3.02 file-existence preprocessor conditions under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import os
import subprocess
import tempfile
from pathlib import Path

from pynasm import Assembler, AssemblyError


def cases(root: Path):
    names = ('"present.bin"', "'present.bin'", '`present.bin`',
             '"absent.bin"', '"include-only.bin"',
             '"source-only.bin"', 'present.bin', '"present.bin" extra', '')
    for directive, name, level in itertools.product(
            ("%iffile", "%ifnfile", "%eliffile", "%elifnfile"),
            names, (0, 9)):
        if directive.startswith("%elif"):
            yield f"%if 0\ndb 3\n{directive} {name}\ndb 1\n%else\ndb 2\n%endif", level
        else:
            yield f"{directive} {name}\ndb 1\n%else\ndb 2\n%endif", level
    absolute = (root / "present.bin").as_posix()
    for level in (0, 9):
        yield f'%iffile "{absolute}"\ndb 1\n%else\ndb 2\n%endif', level
        yield ('%define FILE "present.bin"\n%iffile FILE\ndb 1\n'
               '%else\ndb 2\n%endif'), level


def run(nasm: Path, workers: int = 8) -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        sub, extra = root / "sub", root / "extra"
        sub.mkdir()
        extra.mkdir()
        (root / "present.bin").write_bytes(b"A")
        (sub / "source-only.bin").write_bytes(b"B")
        (extra / "include-only.bin").write_bytes(b"C")
        generated = list(cases(root))

        def compare(case):
            snippet, level = case
            source = "cpu 8086\n" + snippet + "\n"
            # Each worker needs private input/output names while sharing read-only probes.
            with tempfile.TemporaryDirectory(dir=root) as case_dir:
                case_root = Path(case_dir)
                input_file = case_root / "condition.asm"
                output_file = case_root / "condition.bin"
                input_file.write_text(source, encoding="ascii")
                reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                            "-I", str(extra) + "/", "-o", str(output_file),
                                            str(input_file)], cwd=root, capture_output=True,
                                           text=True, timeout=5)
                expected = output_file.read_bytes() if reference.returncode == 0 else None
                try:
                    actual = Assembler(compatibility="nasm3", optimize=level,
                                       include_paths=[extra]).assemble(
                                           source, filename=str(input_file))
                except AssemblyError:
                    actual = None
            if actual != expected:
                actual_text = actual.hex() if actual is not None else "REJECT"
                expected_text = expected.hex() if expected is not None else "REJECT"
                return (f"{snippet!r} -O{level}: "
                        f"Python={actual_text} NASM={expected_text}")
            return None

        old_cwd = Path.cwd()
        os.chdir(root)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                differences = [message for message in executor.map(compare, generated) if message]
        finally:
            os.chdir(old_cwd)
        if differences:
            raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences[:70]))
        return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
