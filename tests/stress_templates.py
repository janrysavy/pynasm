"""Audit representative NASM 3.02 non-FPU 8086 instruction templates.

First expand the pinned x86/insns.dat with NASM's own x86/preinsns.pl, then
pass that expanded file here. Each row is instantiated once in 16-bit mode;
This includes NASM's ECX/RCX shift-count aliases and 32-bit branch-target
templates, which NASM accepts even with ``CPU 8086`` in 16-bit mode.
"""

import argparse
import concurrent.futures
import subprocess
import tempfile
from pathlib import Path

from pynasm import AssemblyError, assemble

try:  # Support both python -m tests.stress_templates and direct execution.
    from .nasm_template_inventory import pinned_templates
except ImportError:
    from nasm_template_inventory import pinned_templates


OPERAND = {
    "rm8": "byte [bx+5]", "rm16": "word [bx+5]",
    "reg8": "cl", "reg16": "cx", "reg_al": "al", "reg_ax": "ax",
    "reg_dx": "dx", "reg_cx": "cx", "reg_bx": "bx", "reg_cl": "cl",
    "reg_ecx": "ecx", "reg_rcx": "rcx", "reg_es": "es", "reg_cs": "cs",
    "reg_ss": "ss", "reg_ds": "ds", "reg_sreg": "ds",
    "mem8": "byte [bx+5]", "mem16": "word [bx+5]",
    "mem": "[bx+5]", "mem_offs": "[0x1234]",
    "imm8": "7", "imm16": "0x1234", "imm": "0x1234",
    "unity": "1", "sbyteword16": "byte 1",
    "imm8|abs": "7", "imm16|abs": "0x1234",
    "imm16|short": "short $+2", "imm16|near": "near $+3",
    "imm16|near|short": "short $+2", "rm16|near": "word [bx+5]",
    "imm32|short": "dword short $+3", "imm32|near": "dword near $+7",
    "imm32|near|short": "dword short $+3",
    "mem16|far": "far [bx+5]", "imm16|far": "far 0x1234:0x5678",
    "imm16:imm16": "0x1234:0x5678",
    "imm16:imm16|far": "far 0x1234:0x5678",
}


def rows(expanded: bytes):
    for row in pinned_templates(expanded):
        if "8086" not in row.flags or any(flag in row.flags for flag in ("APX", "FPU", "OPT")):
            continue
        yield row.line, row.mnemonic, row.operands


def case_for(mnemonic: str, signature: str) -> str:
    mnemonic = "jz" if mnemonic == "Jcc" else mnemonic.lower()
    if signature == "void":
        return mnemonic
    try:
        operands = [OPERAND[token] for token in signature.split(",")]
    except KeyError as exc:
        raise ValueError(f"unmapped 8086 operand template: {signature}") from exc
    return mnemonic + " " + ",".join(operands)


def run(expanded_path: Path, nasm: Path, workers: int = 8) -> tuple[int, int]:
    templates = list(rows(expanded_path.read_bytes()))

    def compare(work):
        level, line_number, mnemonic, signature = work
        case = case_for(mnemonic, signature)
        source = "cpu 8086\nbits 16\n" + case + "\n"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "case.asm"
            output_file = Path(directory) / "case.bin"
            input_file.write_text(source, encoding="ascii")
            reference = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                        "-o", str(output_file), str(input_file)],
                                       capture_output=True, text=True, timeout=3)
            if reference.returncode:
                raise AssertionError(f"NASM rejected legal template at line {line_number}: "
                                     f"{case!r}: {reference.stderr}")
            expected = output_file.read_bytes()
        try:
            actual = assemble(source, compatibility="nasm3", optimize=level)
        except AssemblyError:
            actual = None
        if actual != expected:
            actual_text = actual.hex() if actual is not None else "REJECT"
            expected_text = expected.hex() if expected is not None else "REJECT"
            return (f"line {line_number} -O{level}: {signature} / {case!r}: "
                    f"Python={actual_text} NASM={expected_text}", expected is not None)
        return None, expected is not None

    work = ((level, *row) for level in (0, 1, 9) for row in templates)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(compare, work))
    mismatches = [message for message, _ in results if message]
    if mismatches:
        raise AssertionError(f"{len(mismatches)} mismatches:\n" + "\n".join(mismatches[:70]))
    return len(results), sum(accepted for _, accepted in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded", required=True, type=Path)
    parser.add_argument("--nasm", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    compared, accepted = run(args.expanded, args.nasm, args.workers)
    print(f"compared {compared} row instances; NASM accepted {accepted}")
