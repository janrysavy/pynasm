# Handoff - assembly-aware preprocessing, 2026-09-30

FINISHED locally: issue #19 reproduced against NASM 3.02 and fixed with
per-pass streaming source expansion and actual location/relocation metadata.
294 new independent comparisons pass (234 complete binaries, 60 rejections).
Full native suite: 228 pass/one skip; portable: 204 pass/25 explicit skips.
Evidence and semantics: doc/PREPROCESSOR_LOCATION.md and linked receipt.

WIP publication: push this slice and inspect final Windows/Linux CI before
merging. Other open PRO PRs must be reviewed separately; no claim that their
changes are incorporated yet. Parent pin still refers to the prior master.

Earlier PR16-18 work was integrated through PR20. These assembler checks
are not Pascal/game-mechanics proof; parent parity gates follow pin integration.
