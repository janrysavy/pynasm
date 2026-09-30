# Handoff - assembly-aware preprocessing, 2026-09-30

FINISHED locally: issue #19 reproduced against NASM 3.02 and fixed with
per-pass streaming source expansion and actual location/relocation metadata.
294 new independent comparisons pass (234 complete binaries, 60 rejections).
Full native suite: 228 pass/one skip; portable: 204 pass/25 explicit skips.
Evidence and semantics: doc/PREPROCESSOR_LOCATION.md and linked receipt.

WIP publication: push this slice and inspect final Windows/Linux CI before
merging. PRO PR21 is integrated locally: its four methods pass against native NASM.
PRO PR22 also passes its four native NASM methods and is integrated locally.
PRO PR23 is integrated locally: all 20 combined focused methods pass with NASM.
Only merge conflict was the two required imports, both retained. Full combined
native suite and final Windows/Linux CI remain WIP; do not merge before those pass. Parent pin still refers to the prior master.

Earlier PR16-18 work was integrated through PR20. These assembler checks
are not Pascal/game-mechanics proof; parent parity gates follow pin integration.
