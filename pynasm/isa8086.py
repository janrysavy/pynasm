"""Declarative opcode data for the original 8086/8088 instruction set.

The CPU variants have the same instruction set. Opcodes here are the 8086
subset of the mininasm and NASM instruction databases; no native code is used.
"""

REG8 = {name: index for index, name in enumerate("al cl dl bl ah ch dh bh".split())}
REG16 = {name: index for index, name in enumerate("ax cx dx bx sp bp si di".split())}
SEGREG = {name: index for index, name in enumerate("es cs ss ds".split())}
SEG_PREFIX = {"es": 0x26, "cs": 0x2E, "ss": 0x36, "ds": 0x3E}

FIXED = {
    "aaa": 0x37, "aas": 0x3F, "cbw": 0x98, "clc": 0xF8,
    "cld": 0xFC, "cli": 0xFA, "cmc": 0xF5, "cwd": 0x99,
    "daa": 0x27, "das": 0x2F, "hlt": 0xF4, "int3": 0xCC,
    "into": 0xCE, "iret": 0xCF, "iretw": 0xCF,
    "lahf": 0x9F, "movsb": 0xA4,
    "movsw": 0xA5, "cmpsb": 0xA6, "cmpsw": 0xA7,
    "stosb": 0xAA, "stosw": 0xAB, "lodsb": 0xAC, "lodsw": 0xAD,
    "scasb": 0xAE, "scasw": 0xAF, "nop": 0x90, "popf": 0x9D,
    "pushf": 0x9C, "pushfw": 0x9C, "popfw": 0x9D,
    "sahf": 0x9E, "salc": 0xD6, "xlat": 0xD7,
    "xlatb": 0xD7, "stc": 0xF9, "std": 0xFD, "sti": 0xFB,
    "pause": b"\xF3\x90", "brkpt": 0xCC, "int03": 0xCC,
    "fwait": 0x9B,
}

PREFIX = {
    "lock": 0xF0, "rep": 0xF3, "repe": 0xF3, "repz": 0xF3,
    "repne": 0xF2, "repnz": 0xF2, "wait": 0x9B,
    "bnd": 0xF2, "nobnd": 0,
    **SEG_PREFIX,
}

# base opcode for r/m8,reg8. The other directional and width forms are +1,+2,+3.
ALU = {
    "add": (0x00, 0), "or": (0x08, 1), "adc": (0x10, 2),
    "sbb": (0x18, 3), "and": (0x20, 4), "sub": (0x28, 5),
    "xor": (0x30, 6), "cmp": (0x38, 7),
}

JCC = {
    "jo": 0x70, "jno": 0x71, "jb": 0x72, "jnae": 0x72, "jc": 0x72,
    "jnb": 0x73, "jae": 0x73, "jnc": 0x73, "je": 0x74, "jz": 0x74,
    "jne": 0x75, "jnz": 0x75, "jbe": 0x76, "jna": 0x76,
    "ja": 0x77, "jnbe": 0x77, "js": 0x78, "jns": 0x79,
    "jp": 0x7A, "jpe": 0x7A, "jnp": 0x7B, "jpo": 0x7B,
    "jl": 0x7C, "jnge": 0x7C, "jge": 0x7D, "jnl": 0x7D,
    "jle": 0x7E, "jng": 0x7E, "jg": 0x7F, "jnle": 0x7F,
    "loopne": 0xE0, "loopnz": 0xE0, "loope": 0xE1,
    "loopz": 0xE1, "loop": 0xE2, "jcxz": 0xE3,
    "loopw": 0xE2, "loopew": 0xE1, "loopzw": 0xE1,
    "loopnew": 0xE0, "loopnzw": 0xE0,
}

SHIFT = {"rol": 0, "ror": 1, "rcl": 2, "rcr": 3,
         "shl": 4, "sal": 4, "shr": 5, "sar": 7}
UNARY_GROUP = {"not": 2, "neg": 3, "mul": 4, "imul": 5,
               "div": 6, "idiv": 7}
