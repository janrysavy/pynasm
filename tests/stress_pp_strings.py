"""Compare NASM 3.02 preprocessor string and token directives."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%strcat X 'ab','cd'\ndb X",
    "%strcat X 'a', 'b', 'c'\ndb X",
    "%define A 'ab'\n%strcat X A,'cd'\ndb X",
    "%istrcat X 'ab','cd'\ndb x",
    "%strcat X 'ab',3\ndb 1",
    "%strlen N 'abc'\ndb N",
    "%strlen N ''\ndb N",
    "%define A 'abcd'\n%strlen N A\ndb N",
    "%istrlen N 'abc'\ndb n",
    "%strlen N 123\ndb 1",
    "%substr X 'abcdef',2,3\ndb X",
    "%substr X 'abcdef',2\ndb X",
    "%substr X 'abcdef',0,2\ndb X",
    "%substr X 'abcdef',7,2\ndb X",
    "%substr X 'abcdef',2,-1\ndb X",
    "%substr X 'abcdef',2,-3\ndb X",
    "%substr X 'abcdef',2,0\ndb X",
    "%isubstr X 'abcdef',2,3\ndb x",
    "%substr X 123,1,2\ndb 1",
    "%substr X 'abcdef'\ndb 1",
    "%deftok X '1+2'\ndb X",
    "%deftok X 'mov ax,1'\nX",
    "%ideftok X '1+2'\ndb x",
    "%deftok X 123\ndb 1",
    "%defstr X 1+2\ndb X",
    "%idefstr X 1+2\ndb x",
    "%strlen N `a\\nb`\ndb N",
    "%strcat X `a\\n`,'b'\ndb X",
    "%substr X `ab\\ncd`,3,1\ndb X",
    "%substr X 'abc',-2,2\ndb X",
    "%substr X 'abc',2,-10\ndb X",
    "%substr X 'abcdef',(1+1),(1+1)\ndb X",
    "%substr X 'abc' 2 2\ndb X",
    "%strcat X\ndb X",
    "%deftok X ''\nX\ndb 1",
    "%deftok X 'db 1,2'\nX",
    "%defstr X 'a' + 'b'\ndb X",
    "%strlen N 'abc', 3\ndb N",
    "%deftok X '1+2','3'\ndb X",
    "%substr X 'abcdef' 2,3\ndb X",
    "%substr X 'abcdef' 2, 3\ndb X",
    "%substr X 'abcdef',2 3\ndb X",
    "%substr X 'abcdef' (1+1),3\ndb X",
    "%substr X 'abcdef' 2 + 1,2\ndb X",
    "%substr X 'abcdef',2 + 1,2\ndb X",
    "%substr X 'abcdef',2 3\ndb X",
    "%substr X 'abcdef' 2 3\ndb X",
    "%substr X 'abcdef',2,3 4\ndb X",
    "%substr X 'abcdef',2,3,4\ndb X",
    "%substr X 'abcdef',2,\ndb X",
    "%substr X 'abcdef', 2 + 1\ndb X",
    "%substr X 'abcdef' 2 + 1\ndb X",
    "%substr X 'abcdef',(1 + 1) 3\ndb X",
    "%substr X 'abcdef',2<<1,2\ndb X",
    "%substr X 'abcdef',2*2,2\ndb X",
    "%substr X 'abcdef',-1,2\ndb X",
    "%substr X 'abcdef',-1 2\ndb X",
    "%substr X 'abcdef',2,3 + 1\ndb X",
)


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(itertools.product(SNIPPETS, (0, 1, 9)))
    for value, start, count, level in itertools.product(
            ("''", "'A'", "'ABC'", "'abcdef'"),
            (-3, -1, 0, 1, 2, 3, 4, 7, 10),
            (-10, -4, -1, 0, 1, 2, 4, 10), (0, 9)):
        generated.append((f"%substr X {value},{start},{count}\ndb X", level))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "strings.asm"
            output_file = Path(directory) / "strings.bin"
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
