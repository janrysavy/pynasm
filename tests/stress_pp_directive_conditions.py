"""Compare NASM 3.02 preprocessor directive-name conditions under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


PP_SUFFIXES = ("", "ctx", "def", "defalias", "difi", "directive",
               "empty", "env", "file", "id", "idn", "idni", "macro",
               "num", "str", "token", "usable", "using")
DIRECTIVE_NAMES = (
    "absolute", "bits", "common", "cpu", "debug", "default", "dollarhex",
    "extern", "float", "global", "list", "pragma", "required", "sectalign",
    "section", "segment", "static", "warning", "prefix", "suffix", "postfix",
    "gprefix", "gsuffix", "gpostfix", "lprefix", "lsuffix", "lpostfix",
    "db", "dw", "dd", "dq", "dt", "do", "dy", "dz", "resb", "resw",
    "resd", "resq", "rest", "reso", "resy", "resz", "incbin", "equ",
    "export", "group", "import", "library", "map", "module", "org",
    "osabi", "safeseh", "uppercase", "limit", "options", "nodepend",
)

NAMES = ("bits", "BITS", "section", "org", "map", "export", "db", "resz",
         "incbin", "equ", "prefix", "limit", "nonsense", "", "'bits'",
         '"[bits 16]"', '"[org 0x100]"', '"[export thing]"',
         "%if", "%define", "%ifdef", "%ifdirective", "%fatal",
         "%require", "%pathsearch", "%unknown", "if", "arg",
         "bits extra", "%define extra", "foo bar") + DIRECTIVE_NAMES + tuple(
             "%" + stem + negation + suffix
             for stem in ("if", "elif")
             for negation in ("", "n")
             for suffix in PP_SUFFIXES)


def cases():
    for condition, name, level in itertools.product(
            ("%ifdirective", "%ifndirective", "%elifdirective",
             "%elifndirective"), NAMES, (0, 9)):
        if condition.startswith("%elif"):
            yield (f"%if 0\ndb 3\n{condition} {name}\ndb 1\n"
                   "%else\ndb 2\n%endif"), level
        else:
            yield (f"{condition} {name}\ndb 1\n%else\ndb 2\n%endif"), level
    for level in (0, 9):
        yield ("%define CHECK org\n%ifdirective CHECK\ndb 1\n"
               "%else\ndb 2\n%endif"), level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        snippet, level = case
        source = "cpu 8086\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file, output_file = Path(directory) / "directive.asm", Path(directory) / "directive.bin"
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
