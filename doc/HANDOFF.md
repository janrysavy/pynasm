# Handoff - remaining PRO takeover, 2026-09-30

FINISHED: PR25 percent-token boundaries are merged into this integration branch.
Four focused methods pass with native NASM 3.02, including 240 oracle cases;
legacy compatibility and inactive/macro/string contexts remain covered.
Earlier PR24 and issue19 are integrated on master; their evidence is unchanged.

FINISHED: PR26 expression parsing also passes six focused methods, including
96 native NASM outcomes at O0/O1/O9. Both original PR heads are retained.

FINISHED: the unfinished first-pass branch is preserved. All 435 historical
native outcomes were reproduced; its source digest was corrected to an explicit
JSON encoding. Before repair, pynasm disagreed on 84 of 145 cases; all now agree.

FINISHED: generic UNKNOWN-vector cancellation, EQU projection and immediate
TIMES validation. Full final native suite: 258 methods, 257 passed/one optional
skip. Four new regression methods pass 870 Python and 435 native corpus checks.
Details: doc/PRO_REMAINDER_TIMES.md; full log in its compressed receipt.

WIP: final Windows/Linux CI must pass on this exact head before merge/pinning.
Do not infer Pascal or gameplay proof from assembler tests.
