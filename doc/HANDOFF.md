# Handoff - PR24 integrated, 2026-09-30

FINISHED: PR24 merged as 2e2f8ea after Windows/Linux checks passed on its
final head 5d5c562. Original PR21-23 heads are ancestors of master; their
fixes are retained, and GitHub marked all three PRs merged automatically.
Issue #19 is resolved with assembly-aware preprocessing and location metadata.

Native NASM suite: 244 methods, 243 passed/one optional corpus skip. All 294
location-context outcomes agree, and the full 3,091-byte DOSCTRL worker
retains the historical byte/hash identity. Evidence and full logs:
doc/PREPROCESSOR_LOCATION.md and its linked receipt.

Other PRO work is still running; preserve its feature/transfer branches.
This commit only refreshes the merge state; parent pin and full parent checks
are handled in the parent HANDOFF. Do not infer new Pascal translation or
gameplay evidence from assembler validation.
