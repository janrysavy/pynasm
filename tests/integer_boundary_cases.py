"""Deterministic 8086 integer boundaries; no SUT opcode tables are imported."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

REG8 = tuple("al cl dl bl ah ch dh bh".split())
REG16 = tuple("ax cx dx bx sp bp si di".split())
ALU = tuple("add or adc sbb and sub xor cmp".split())
UNARY = tuple("inc dec not neg mul imul div idiv".split())
SHIFT = tuple("rol ror rcl rcr shl sal shr sar".split())
BASES = ("bx", "bp", "si", "di", "bx+si", "bx+di", "bp+si", "bp+di")
SEGMENTS = ("", "es:", "cs:", "ss:", "ds:")
DISPLACEMENTS = (-32769, -129, -128, -1, 0, 1, 127, 128, 32767, 32768,
                 65407, 65408, 65535, 65536)


@dataclass(frozen=True)
class Case:
    family: str
    source: str


def legal_cases(full: bool = False):
    # Exhaustive register pairs, including high byte registers and AX versus
    # non-accumulator XCHG/ALU alternatives. No random-prefix truncation.
    for mnemonic in (*ALU, "mov", "test", "xchg"):
        for registers in (REG8, REG16):
            for dst, src in product(registers, repeat=2):
                yield Case("register-pairs", f"{mnemonic} {dst},{src}")
    disps = DISPLACEMENTS if full else (-129, -128, 0, 127, 128, 65535)
    unary = UNARY if full else ("inc", "mul", "idiv")
    shifts = SHIFT if full else ("rcl", "sar")
    for base, displacement, segment in product(BASES, disps, SEGMENTS):
        address = f"[{segment}{base}+({displacement})]"
        for width in ("byte", "word"):
            for mnemonic in unary:
                yield Case("memory-unary", f"{mnemonic} {width} {address}")
            for mnemonic, count in product(shifts, ("1", "cl")):
                yield Case("memory-shifts", f"{mnemonic} {width} {address},{count}")
        for mnemonic in ("push", "pop", "jmp", "call"):
            yield Case("memory-stack-transfer", f"{mnemonic} word {address}")
        for mnemonic in ("jmp", "call"):
            yield Case("memory-far-transfer", f"{mnemonic} far {address}")
    # disp16-only mode versus accumulator moffs and the BP zero-displacement
    # escape. Explicit BYTE/WORD displacement hints compete with defaults.
    for number, segment in product((0, 127, 128, 65535), SEGMENTS):
        for hint in ("", "byte ", "word "):
            address = f"[{segment}{hint}{number}]"
            for register in ("al", "ah", "ax", "di"):
                yield Case("direct-address", f"mov {register},{address}")
                yield Case("direct-address", f"mov {address},{register}")
    values = (-129, -128, -1, 0, 1, 127, 128, 255, 32767, 32768, 65408, 65535)
    destinations = (*REG16, "word [bx]", "word [bp]") if full else (
        "ax", "bx", "word [bp]")
    for mnemonic, dst, value, qualifier in product(
            ALU, destinations, values, ("", "word ", "strict word ", "byte ")):
        yield Case("alu-immediate-selection", f"{mnemonic} {dst},{qualifier}{value}")
    for order in ("lock es", "es lock", "rep es", "es rep", "rep lock", "lock rep"):
        for instruction in ("add word [bx],127", "xchg word [bp],ax"):
            yield Case("prefix-order", f"{order} {instruction}")


# Each pair has an explicit accepted control and a nearby rejected form. The
# rejected side is checked separately; 'both rejected' can never pass a pair.
CPU_PAIRS = (
    ("push ax", "push 1"),
    ("pop ax", "pusha"),
    ("pop bx", "popa"),
    ("shl ax,1", "shl ax,2"),
    ("imul bx", "imul ax,bx"),
    ("imul bx", "imul ax,bx,7"),
    ("mov ax,bx", "mov eax,ebx"),
    ("inc word [bx]", "inc dword [bx]"),
    ("mov ax,[bx+si]", "mov ax,[bx+bp]"),
    ("mov ax,[bx+di]", "mov ax,[si+di]"),
    ("mov ax,[si]", "mov ax,[si*2]"),
    ("in al,dx", "insb"),
    ("out dx,al", "outsb"),
    ("push bp", "enter 8,0"),
    ("pop bp", "leave"),
    ("cmp ax,bx", "bound ax,[bx]"),
    ("cli", "lgdt [bx]"),
    ("nop", "bswap eax"),
    ("cbw", "movzx ax,bl"),
    ("test ax,bx", "bt ax,bx"),
    ("or ax,bx", "setnz al"),
)

# NASM's CPU directive does not police every address-size prefix. These are
# intentional project rejections, not positive byte-parity comparisons.
STRICT_CPU_DIVERGENCES = (("mov ax,[eax]", "678b00"),)
