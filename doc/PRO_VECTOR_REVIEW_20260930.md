# Native review of PRs #16–#18, 2026-09-30

All three original heads are preserved in this integration branch. Native
NASM 3.02 on Windows freshly replayed their portable expectations: ternary
scalar conditions (93 native outcomes), vector comparisons (1,986), section
provenance/ABSOLUTE expressions (558). Both 8086/8088 aliases replay the
same portable cases. The combined native-enabled suite passes 224 methods
with one optional external-corpus skip; no production repair was needed.
Native logs, oracle identity and original heads:
doc/evidence/pro_vector_review_20260930.json.gz.

The fixes preserve section identity separately from layout provenance,
compare symbolic vectors and reject non-scalar ternary conditions. EQU
self-relative handling and speculative ABSOLUTE location evaluation now
follow the pinned reference. These are assembler results, not evidence of
new Pascal translation or runtime behavior. Final Windows/Linux integration
CI passed on 069e70f. Portable suite: 200 passed, 24 explicit optional
skips. Final documentation-head CI and merge still follow. The one-off input
packaging branch is not included in the integration.
