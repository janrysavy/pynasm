"""Semantic inventory of the pinned NASM 3.02 expanded instruction table.

Perl's hash iteration can spell the same flags SM0-1 or SM0,SM1 in different
orders. Pin the table's meaning, not that nondeterministic presentation.
The inventory is evidence about source forms, not proof that a specific NASM
encoding alternative was selected for an ambiguous form.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

NASM_COMMIT = "4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065"
INSNS_SHA256 = "34c98c66fb85e08655823f1fb8e267ca61af5b172e97f2220efedc7ac8f81571"
SEMANTIC_SHA256 = "4221f47390b5225299762921d4a05dfdeb4e46769fb45a5995298d6dd5927dce"


@dataclass(frozen=True)
class Template:
    line: int
    mnemonic: str
    operands: str
    encoding: str
    flags: tuple[str, ...]

    @property
    def scope(self) -> str:
        if "FPU" in self.flags:
            return "8087-deferred"
        if "imm32" in self.operands:
            return "later-width-branch-excluded"
        if self.mnemonic in ("MOVZX", "MOVZXD"):
            return "optimizer-source32-open"
        return "integer-8086"

    def semantic(self) -> list:
        return [self.mnemonic, self.operands, self.encoding, list(self.flags)]


def normalized_flags(text: str) -> tuple[str, ...]:
    flags = set()
    for flag in text.split(","):
        match = re.fullmatch(r"([A-Z_]+)(\d+)-(\d+)", flag)
        if match:
            first, last = int(match[2]), int(match[3])
            if first > last or last - first > 64:
                raise ValueError(f"invalid NASM flag range: {flag}")
            flags.update(f"{match[1]}{index}" for index in range(first, last + 1))
        else:
            flags.add(flag)
    return tuple(sorted(flags))


def parse_table(expanded: bytes) -> list[Template]:
    templates = []
    for number, line in enumerate(expanded.decode("ascii").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        fields = stripped.split()
        if len(fields) < 4:
            raise ValueError(f"malformed expanded NASM row at line {number}")
        templates.append(Template(number, fields[0], fields[1],
                                  " ".join(fields[2:-1]),
                                  normalized_flags(fields[-1])))
    return templates


def semantic_digest(templates: list[Template]) -> str:
    canonical = json.dumps([row.semantic() for row in templates],
                           separators=(",", ":")).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def pinned_templates(expanded: bytes) -> list[Template]:
    templates = parse_table(expanded)
    if semantic_digest(templates) != SEMANTIC_SHA256:
        raise ValueError("expanded insns.dat semantics differ from pinned NASM 3.02")
    return templates


def inventory(expanded: bytes) -> dict:
    rows = []
    for row in pinned_templates(expanded):
        if "8086" not in row.flags:
            continue
        rows.append({"line": row.line, "mnemonic": row.mnemonic,
                     "operands": row.operands, "encoding": row.encoding,
                     "flags": list(row.flags), "scope": row.scope,
                     "boundary_coverage": "open"})
    return {"schema": 1, "nasm_commit": NASM_COMMIT,
            "insns_sha256": INSNS_SHA256, "semantic_sha256": SEMANTIC_SHA256,
            "rows": rows}
