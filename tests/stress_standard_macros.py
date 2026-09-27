"""Compare NASM 3.02 standard section/alignment macros under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%ifdef __?SECT?__\ndb 1\n%endif",
    "%ifdef __SECT__\ndb 1\n%endif",
    "%if __?SECTALIGN_ALIGN_UPDATES_SECTION?__\ndb 1\n%endif",
    "%if __SECTALIGN_ALIGN_UPDATES_SECTION__\ndb 1\n%endif",
    "section .data\n[section .text]\ndb 1\n__SECT__\ndb 2",
    "segment .data\n[section .text]\ndb 1\n__?SECT?__\ndb 2",
    "[section .data]\n[section .text]\ndb 1\n__SECT__\ndb 2",
    "sectalign off\n%if __?SECTALIGN_ALIGN_UPDATES_SECTION?__\n"
    "db 1\n%else\ndb 2\n%endif",
    "sectalign off\n%if __SECTALIGN_ALIGN_UPDATES_SECTION__\n"
    "db 1\n%else\ndb 2\n%endif",
    "sectalign off\nsectalign on\n%if __SECTALIGN_ALIGN_UPDATES_SECTION__\n"
    "db 1\n%else\ndb 2\n%endif",
    "org 0x101\nsectalign off\ndb 1\nalign 16\ndb 2",
    "org 0x101\nsectalign on\ndb 1\nalign 16\ndb 2",
    "org 0x101\nsectalign off\n%use smartalign\n"
    "alignmode generic,nojmp\ndb 1\nalign 16\ndb 2",
    "org 0x101\n%use smartalign\nsectalign off\n"
    "alignmode generic,nojmp\ndb 1\nalign 16\ndb 2",
    "org 0x101\nsectalign off\ndb 1\nalignb 16\ndb 2",
)


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(itertools.product(SNIPPETS, (0, 1, 9)))
    for origin, boundary, automatic, lead, directive, level in itertools.product(
            (0x101, 0x103, 0x110), (4, 8, 16), ("on", "off"),
            (0, 1, 5), ("align", "alignb"), (0, 9)):
        generated.append((f"org {origin}\nsectalign {automatic}\n"
                          f"times {lead} db 0\n{directive} {boundary}\ndb 0xaa", level))
    for automatic, boundary, directive, level in itertools.product(
            ("on", "off"), (0, 1, 3, 6, 7),
            ("align", "alignb"), (0, 9)):
        generated.append((f"sectalign {automatic}\ndb 1\n"
                          f"{directive} {boundary}\ndb 2", level))
    for boundary, level in itertools.product((0, 1, 3, 6, 7), (0, 9)):
        generated.append(("sectalign off\n%use smartalign\ndb 1\n"
                          f"align {boundary}\ndb 2", level))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "standard.asm"
            output_file = Path(directory) / "standard.bin"
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
            return (f"{snippet!r} -O{level}: "
                    f"Python={actual.hex() if actual is not None else 'REJECT'} "
                    f"NASM={expected.hex() if expected is not None else 'REJECT'} "
                    f"diagnostic={reference.stderr.strip()!r}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        differences = [message for message in executor.map(compare, generated) if message]
    if differences:
        raise AssertionError(f"{len(differences)} mismatches:\n" + "\n".join(differences))
    return len(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(f"compared {run(args.nasm, args.workers)} cases")
