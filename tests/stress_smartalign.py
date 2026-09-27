"""Compare NASM 3.02 smartalign 16-bit output under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


def cases():
    for mode, boundary, lead, threshold, level in itertools.product(
            ("nop", "generic", "k7", "k8", "p6"),
            (16, 32, 128), (1, 2, 7, 15, 31, 63),
            ("", ",8", ",nojmp"), (0, 1, 9)):
        yield (f"%use smartalign\nalignmode {mode}{threshold}\n"
               f"times {lead} db 0\nalign {boundary}\ndb 0xaa"), level
    for snippet, level in itertools.product(
            ("%use smartalign\ndb 1\nalign 8\ndb 2",
             "%use smartalign\nalignmode generic\ndb 1\n"
             "align 8,db 0xcc\ndb 2",
             "%use smartalign\nalignmode generic,nojmp\ndb 1\n"
             "align 8\ndb 2",
             "%use smartalign\nalignmode unknown\ndb 1"), (0, 1, 9)):
        yield snippet, level
    for boundary, lead, level in itertools.product(
            (256, 512), (1, 127, 255), (0, 1, 9)):
        yield (f"%use smartalign\nalignmode generic,8\n"
               f"times {lead} db 0\nalign {boundary}\ndb 0xaa"), level
    for snippet, level in itertools.product(
            ("org 0x101\n%use smartalign\nalignmode generic,nojmp\n"
             "db 1\nalign 16\ndb 2",
             "section .text\n%use smartalign\nalignmode k8,nojmp\n"
             "db 1\nalign 16\ndb 2",
             "%use smartalign\nalignmode p6,0\ndb 1\nalign 16\ndb 2"),
            (0, 9)):
        yield snippet, level
    for before, after, lead, level in itertools.product(
            ("nop", "generic", "k7", "k8", "p6"),
            ("nop", "generic", "k7", "k8", "p6"),
            (1, 7, 15), (0, 9)):
        yield (f"%use smartalign\nalignmode {before},nojmp\n"
               f"alignmode {after},nojmp\ntimes {lead} db 0\n"
               "align 32\ndb 0xaa"), level
    for snippet, level in itertools.product(
            ("db 1\nalign 8\n%use smartalign\n"
             "alignmode k7,nojmp\ndb 2\nalign 16\ndb 3",
             "%use smartalign\nalignmode k8,nojmp\n"
             "%use smartalign\ndb 1\nalign 16\ndb 2",
             "%use smartalign\nalignmode p6,nojmp\n"
             "db 1\nalignb 8\ndb 2",
             "%use smartalign\n%ifdef __?ALIGNMODE?__\ndb 1\n%endif\n"
             "%ifdef __ALIGNMODE__\ndb 2\n%endif\n"
             "db __?ALIGN_JMP_THRESHOLD?__\n"
             "alignmode k8,nojmp\ndb __?ALIGN_JMP_THRESHOLD?__"), (0, 9)):
        yield snippet, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file, output_file = Path(directory) / "smartalign.asm", Path(directory) / "smartalign.bin"
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
