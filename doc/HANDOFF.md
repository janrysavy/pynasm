# Current state

CLI compatibility slice: NASM lowercase `-i` now accepts separate and attached
include paths, preserving search order. Failed assembly removes stale/partial
output; the main source and its hard-link aliases are protected from overwrite.
Regression tests reproduced the missing alias, stale output and source overwrite
before the fix. Windows/Linux CI runs the standard-library unittest suite.

Flat binaries remain the only output format. NASM listings and OMF objects are
not implemented by this slice. Keep output separate from included input files.

Local validation: 142 tests ran, 123 passed and 19 optional tests skipped.
CLI regressions include hard-link protection and simulated partial-write cleanup.
