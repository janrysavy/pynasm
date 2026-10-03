# Far immediate offset qualifiers, 2026-10-03

Pyro's complete ASM rebuild exposed `call word 0x133a:word 0x934` failing
with `unexpected token '0x934'`. NASM 3.02 accepts it and emits
`9a34093a13`. The offset was evaluated directly as an expression, leaving
`word` unparsed. It now uses the ordinary operand parser and requires an
immediate with a valid 8086 size. Both segment and offset size qualifiers
are checked; invalid byte/dword forms remain rejected.

`tests/fixtures/generated/far_offset_qualifiers.json` captures 128 independent
NASM 3.02 outcomes for CALL/JMP and qualifiers on either half. The regression
replays them at O0/O1/O9 with both CPU aliases (768 comparisons) and optionally
checks all 384 reference outcomes live. Before the fix, the portable test
reported 372 failing comparisons; after it, both test methods pass.

Local full suite under PyPy 3.12 with NASM 3.02: 260 test methods, 259 passed,
one optional independent-corpus skip. Pyro's complete load image (86,192 bytes)
and wrapped EXE (95,280 bytes) also match the unchanged baseline with both
assemblers. Evidence is retained in the parent repository under
`docs/evidence/assembler_backends_20261003/` after integrating this fix.

Run `python -m unittest discover -s tests`; set `NASM` to a NASM 3.02
executable to enable the live reference checks. This establishes compatibility
for the exercised syntax, not complete NASM compatibility.
