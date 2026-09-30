# Handoff - remaining PRO takeover, 2026-09-30

FINISHED: PR25 percent-token boundaries are merged into this integration branch.
Four focused methods pass with native NASM 3.02, including 240 oracle cases;
legacy compatibility and inactive/macro/string contexts remain covered.
Earlier PR24 and issue19 are integrated on master; their evidence is unchanged.

FINISHED: PR26 expression parsing also passes six focused methods, including
96 native NASM outcomes at O0/O1/O9. Both original PR heads are retained.

FINISHED: the unfinished first-pass branch is preserved. All 435 historical
native outcomes were reproduced; its source digest was corrected to an explicit
JSON encoding. Pynasm disagrees on 84 of 145 cases before a fix.

WIP: fix first-pass TIMES unknown-vector cancellation/defined EQU semantics, then
run the full native suite and final Windows/Linux CI before merging/pinning.
Do not infer Pascal or gameplay proof from assembler tests.
