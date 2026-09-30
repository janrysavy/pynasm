# Handoff — native-tested PR integration, 2026-09-30

FINISHED: original PR heads #3–#13 are all preserved. #11's failing regression
is repaired; combining #10/#13 needed a forward-reservation repair. Historical
profile behavior stays unchanged. Native NASM 3.02 agrees on 215,880 integer,
1,440 interaction and 300 branch comparisons, plus 1,011 template outcomes,
96 freshly regenerated program-fixture outcomes and 3,288 address replay cases.
Native-enabled suite: 215 methods, 214 pass, one optional corpus skip.
Portable suite: 195 pass, 19 native-oracle methods and one corpus skipped.
Exact scope/exclusions and receipts: doc/PR_REVIEW_20260930.md, doc/evidence/.

WIP: final documentation-head Windows/Linux CI, merge PR #14, close superseded
drafts and delete their branches. The parent integrates the merged pin after
its own checks. No remote merge has happened at this commit.
