# PRO remainder and TIMES completion, 2026-09-30

PR25 rejects unexpanded percent macro parameters/local labels in active source,
while retaining signed remainder, quotes, inactive branches and valid macro
expansion. PR26 parses TIMES counts with expression grammar and retains other
prefixes. Their original heads are ancestors of this integration branch.

The abandoned first-pass branch provided 145 programs and expected NASM outputs,
but no production fix or runnable regression gate. Fresh native NASM 3.02
confirmed all 435 outputs at O0/O1/O9. Its unexplained source digest was replaced
by an explicit compact-JSON SHA256. Before repair, pynasm disagreed on 84 cases.

The repair carries NASM's UNKNOWN vector coefficient through scalar expression
arithmetic: subtraction and zero multiplication can cancel it; other scalar
operators retain an unknown obligation. Conditional selection propagates the
selected result. TIMES rejects a still-unknown expression immediately, including
overridden TIMES prefixes. EQU follows NASM's published segment/offset placeholder
projection, and later passes replace the value. The historical profile is unchanged.
There are no source-spelling exceptions or case-specific output substitutions.

References: [NASM 3.02 expression evaluator](https://github.com/netwide-assembler/nasm/blob/nasm-3.02/asm/eval.c),
[parser](https://github.com/netwide-assembler/nasm/blob/nasm-3.02/asm/parser.c),
[EQU projection](https://github.com/netwide-assembler/nasm/blob/nasm-3.02/asm/assemble.c).
The fixture pins the native executable hash, source list and all outcomes;
`tests/test_critical_times.py` checks both Python CPU aliases at all three levels
and independently reruns the optional live native oracle.

Validation: full pre-regression native suite 254 methods, 253 passed/one optional
corpus skip. Final native suite: 258 methods, 257 passed/one optional skip. Full native log
and the 84 pre-repair mismatches: `PRO_REMAINDER_TIMES_RECEIPT.json.gz`.
Windows/Linux CI must pass on the final code head before integration.
