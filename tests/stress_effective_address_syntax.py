"""Compare 8086 effective-address arithmetic and register syntax with NASM."""

import argparse
import concurrent.futures
import itertools
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble


ADDRESSES = (
    "bx", "bp", "si", "di", "bx+si", "si+bx", "bp+di+5",
    "bx*1", "1*bx", "bx*0", "0*bx", "bx*0+si", "bx+si*1",
    "bx+1*si", "1*bx+si", "bx*1+si*1", "bx*2", "2*bx",
    "si*2", "2*si", "bx+bx", "si+si", "bx+2*si", "2*si+bx",
    "bx-si", "bx+(-si)", "bx+(-1)", "bx+si+(-1)",
    "(bx)", "(bx+si)", "bx+(si)", "(bx)+si", "(1*bx)+si",
    "bx+0*si", "sp*0", "sp*0+bx", "ax*0+bx",
    "bx+0x7f", "bx+0x80", "bx-0x81", "bx+65536",
    "bx+si+5*2", "bx+si+(3<<2)", "5+bx", "5+bx+si",
    "1*(bx)", "bx*(1)", "0*(bx)", "(0)*bx",
    "2*bx-bx", "bx+bx-bx", "2*si-si", "2*bx-1*bx",
    "bx*2-bx", "bx+0x0*si", "bx+0x1*si",
    "(bx+si)*1", "1*(bx+si)", "0*(bx+si)",
    "bx*(1+0)", "bx*(2-1)", "bx*2/2",
    "bx+bp-bp", "si+di-di", "bx*0+sp*0", "ax-ax", "bx-bx+si",
)
TEMPLATES = ("mov ax,[{a}]", "mov byte [{a}],1", "lea ax,[{a}]")


def cases():
    for address, template, level in itertools.product(ADDRESSES, TEMPLATES, (0, 1, 9)):
        yield template.format(a=address), level
    for source, level in itertools.product(
            ("mov ax,0[bx]", "mov ax,5[bx]", "mov ax,128[bx]",
             "mov ax,-1[bx]", "mov ax,(2+3)[bx+si]",
             "mov ax,0x1234[bx]", "mov ax,5[bx+si]",
             "mov ax,5[es:bx]", "mov ax,es:5[bx]",
             "mov ax,word 5[bx]", "mov ax,5[byte bx]",
             "mov ax,5[word bx]", "mov ax,5[dword 0x1234]",
             "mov ax,5[0x1234]", "mov ax,5[bx*0]",
             "mov ax,5[ax-ax]", "mov ax,5[bx+si+2]",
             "mov ax,5[a32 0x1234]", "mov ax,5[bx][si]",
             "mov ax,5[bx]+1", "mov byte 5[bx],1",
             "lea ax,5[bx]", "fadd dword 5[bx]",
             "mov ax,bx[si]", "mov ax,si[bx]",
             "mov ax,(bx+1)[si]", "mov ax,(2*bx-bx)[si]",
             "mov ax,es:bx[si]", "mov ax,5[cs:bx]",
             "mov ax,target[bx]\ntarget: nop",
             "target: nop\nmov ax,target[bx]",
             "mov ax,target[dword 0x10]\ntarget: nop",
             "mov ax,target[byte bx]\ntarget: nop",
             "mov ax,target[word bx]\ntarget: nop",
             "mov ax,[bx+target]\ntarget: nop",
             "mov ax,(target-$$)[bx]\ntarget: nop",
             "mov ax,target[bx+si]\ntarget: nop"),
            (0, 1, 9)):
        yield source, level


def run(nasm: Path, workers: int = 8) -> int:
    generated = list(cases())

    def compare(case):
        instruction, level = case
        source = "cpu 8086\n" + instruction + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "ea.asm", path / "ea.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=3)
            expected = output_file.read_bytes() if reference.returncode == 0 else None
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            actual_text = actual.hex() if actual is not None else "REJECT"
            expected_text = expected.hex() if expected is not None else "REJECT"
            return (f"{instruction!r} -O{level}: "
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
