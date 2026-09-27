"""Compare NASM 3.02 MASM compatibility macros under CPU 8086."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


SNIPPETS = (
    "%use masm",
    "%use MASM\n%ifusing masm\ndb 1\n%endif",
    "%use masm\n%use masm\ndb 1",
    "%use masm\nstart proc far\nret\nstart endp",
    "%use masm\nstart proc near\nret 4\nstart endp",
    "%use masm\nproc far\nret\nendp\nret",
    "%use masm\nfoo segment\ndb 1\nfoo ends",
    "%use masm\nsegment foo\ndb 1",
    "%use masm\nmov ax,offset foo\nfoo: db 1",
    "%use masm\nmov ax,word ptr [bx]",
    "%use masm\nfld tbyte ptr [bx]",
    "%use masm\nfld st(0)",
    "%use masm\nend\ndb 1",
    "%use masm\n%ifmacro proc 0-*\ndb 1\n%endif",
    "%use vtern\n%ifusing vtern\ndb 1\n%endif",
    "%use masm\nproc far\nret 2\nendp\nret 2",
    "%use masm\nproc near,far\nret\nendp",
    "%use masm\nproc far,near\nret\nendp",
    "%use masm\nproc\nret\nendp",
    "%use masm\nendp\nret",
    "%use MASM\nSTART PROC FAR\nRET\nSTART ENDP",
    "%use masm\nfoo segment align=16\ndb 1\nfoo ends",
    "%use masm\nfoo segment\ndb 1\nends foo\nbar segment\ndb 2",
    "%use masm\nmov ax,OFFSET label\nlabel: db 1",
    "%use masm\nmov byte ptr [bx],1",
    "%use masm\nmov word ptr [bx],ax",
    "%use masm\nfstp st(1)",
    "%use masm\n%ifdef ptr\ndb 1\n%endif\n%ifdef offset\ndb 2\n%endif",
    "%use masm\n%ifdef tbyte\ndb 1\n%endif\n%ifdef flat\ndb 2\n%endif",
    "%use masm\n%ifmacro segment 0-1\ndb 1\n%endif",
    "%use masm\n%ifmacro ends 0-*\ndb 1\n%endif",
    "%use masm\n%ifmacro endp 0\ndb 1\n%endif",
    "%use vtern\n%ifdef __?USE_VTERN?__\ndb 1\n%endif",
    "%use vtern\n%ifmacro vpternlogd 4\ndb 1\n%endif",
    "%use masm\nmov ax,flat foo\nfoo: db 1",
    "%use masm\nmov ax,ptr [bx]",
    "%use masm\nmov ax,ptr foo\nfoo: db 1",
    "%use masm\nmov ax,byte ptr [bx]",
    "%use masm\nmov ax,word ptr foo\nfoo: db 1",
    "%use masm\nmov ax,offset [bx]",
    "%use masm\nmov ax,offset 5",
    "%use masm\nmov word ptr [bx],offset foo\nfoo: db 1",
    "%use masm\nmov ax,tbyte ptr [bx]",
    "%use masm\nmov ax,flat:[bx]",
    "%use masm\nfld ST(7)",
    "%use vtern\nvpternlogd ax,bx,cx,1",
    "%use masm\nmov ax,foo ptr\nfoo: db 1",
    "%use masm\nmov ax,[bx] ptr",
    "%use masm\nmov ax,ptr word foo\nfoo: db 1",
    "%use masm\nmov ax,ptr byte foo\nfoo: db 1",
    "%use masm\nmov ax,ptr bx",
    "%use masm\nmov ax,word ptr bx",
)


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(itertools.product(SNIPPETS, (0, 1, 9)))

    def compare(case):
        snippet, level = case
        source = "cpu 8086\nbits 16\n" + snippet + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "masm.asm"
            output_file = Path(directory) / "masm.bin"
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
