"""Regenerate the 8087 opcode tables from the pinned NASM 3.02 insns.dat."""

from __future__ import annotations

import argparse
import hashlib
import pprint
import re
from pathlib import Path


INSNS_SHA256 = "34c98c66fb85e08655823f1fb8e267ca61af5b172e97f2220efedc7ac8f81571"


def generate(source: Path, destination: Path) -> None:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INSNS_SHA256:
        raise ValueError("insns.dat differs from the pinned NASM 3.02 revision")
    fixed: dict[str, bytes] = {}
    memory: dict[str, dict[int | None, tuple[bytes, int, int]]] = {}
    registers: dict[str, dict[str, tuple[int, int]]] = {}
    count = 0
    for line in raw.decode("ascii").splitlines():
        if line.lstrip().startswith(";"):
            continue
        fields = [field.strip() for field in re.split(r"\t+", line) if field.strip()]
        if len(fields) != 5 or not {"8086", "FPU"}.issubset(fields[4].split(",")):
            continue
        mnemonic, operands = fields[0].lower(), fields[1]
        encoding = fields[3].removesuffix("]").split()
        prefix = b"\x9b" if encoding[:1] == ["wait"] else b""
        if prefix:
            encoding.pop(0)
        if operands == "void":
            fixed[mnemonic] = prefix + bytes.fromhex("".join(encoding))
        elif operands.startswith("mem"):
            width = int(operands[3:]) if operands[3:] else None
            if len(encoding) != 2 or not re.fullmatch(r"/[0-7]", encoding[1]):
                raise ValueError(f"unexpected memory encoding: {line}")
            memory.setdefault(mnemonic, {})[width] = (prefix, int(encoding[0], 16),
                                                        int(encoding[1][1:]))
        elif "fpureg" in operands:
            if prefix or len(encoding) != 2 or not re.fullmatch(r"[0-9a-f]{2}\+r", encoding[1]):
                raise ValueError(f"unexpected register encoding: {line}")
            registers.setdefault(mnemonic, {})[operands] = (int(encoding[0], 16),
                                                              int(encoding[1][:2], 16))
        else:
            raise ValueError(f"unexpected FPU form: {line}")
        count += 1
    if count != 162:
        raise ValueError(f"expected 162 8086/FPU rows, found {count}")
    header = ('"""8087 encodings generated from NASM 3.02 x86/insns.dat.\n\n'
              f'Source SHA-256: {INSNS_SHA256}. Run tools/generate_fpu.py to regenerate.\n'
              'NASM data is BSD-2-Clause; see doc/NASM_LICENSE.\n"""\n\n')
    body = ""
    for name, data in (("FPU_FIXED", fixed), ("FPU_MEMORY", memory), ("FPU_REGISTER", registers)):
        body += f"{name} = {pprint.pformat(data, sort_dicts=True, width=100)}\n\n"
    body += "FPU_MNEMONICS = frozenset(FPU_FIXED) | frozenset(FPU_MEMORY) | frozenset(FPU_REGISTER)\n"
    destination.write_text(header + body, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("insns", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate(args.insns, args.output)
