# Current state

CLI compatibility slice: NASM lowercase `-i` now accepts separate and attached
include paths, preserving search order. Failed assembly removes stale/partial
output; the main source and its hard-link aliases are protected from overwrite.
Regression tests reproduced the missing alias, stale output and source overwrite
before the fix. Windows/Linux CI runs the standard-library unittest suite.

Expanded-source listings are now available through `-l` and `Assembler.listing`.
They retain final-pass bytes, source locations, section offsets and separate
physical/virtual addresses. BSS/ABSOLUTE reservations carry no file bytes.
Seven listing tests cover native NASM instruction rows, branch relaxation,
includes/macros/INCBIN, sections, wrapping, stale state and failed-write cleanup.
This is not NASM's macro/include event listing; see README for parser limits.
Flat binaries remain the only output format; OMF is not implemented.
Keep outputs separate from included input files.

Local validation: 142 tests ran, 123 passed and 19 optional tests skipped.
CLI regressions include hard-link protection and simulated partial-write cleanup.

The first Windows CI run exposed CRLF conversion of binary goldens and an
incompatible preinstalled NASM oracle. Fixtures now disable Git text conversion;
CI explicitly disables live NASM discovery with an empty NASM variable. Live
differential tests require the documented NASM 3.02 reference executable.

Listing slice validation: 149 tests ran with NASM 3.02, 148 passed and one
optional external-corpus test skipped. Downstream Pyro validation accounts for
all 86,192 image bytes exactly once through listing records; image, wrapped EXE
and Shift/LED carrier bytes remain unchanged.
