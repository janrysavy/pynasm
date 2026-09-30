# Location-sensitive preprocessing (issue #19)

The `nasm3` profile now expands source during each assembly pass. A `%if`,
`%assign` or `%rep` expression sees the current location and the assembler's
symbol/section relocation metadata. Branch-size changes cause preprocessing
and layout to converge together; the final listing uses that same expansion.
The legacy `nasm09839` profile retains preprocessing before assembly.

`$` and labels in normal sections remain relocatable, even after `ORG`:
NASM rejects them as bare scalar preprocessor expressions. Differences within
one section, such as `$-$$` and `last-first`, are valid scalars. `ABSOLUTE 32`
creates an absolute location which reservations advance; `ABSOLUTE label`
retains the label's relocation status. Switching sections restores that
section's own position. Forward `follows`/`vfollows` declarations are supported;
a dependency never declared by the active source is rejected.

Preprocessor warnings are emitted from the final converged pass once. Repeated
warnings within a macro or `%rep` still produce repeated events.

`tests/fixtures/preprocessor_location.json.gz` stores 294 captured outcomes
from NASM 3.02: 234 full binaries and 60 diagnostic rejections. Coverage includes
absolute offsets/reservations, relocatable contexts, labels/aliases, section
switches, BSS, includes, macros, repetition and optimization levels 0/1/9.
NASM calls this instruction set `8086`; its results also check pynasm's `8088`
alias. This is tested scope, not a claim of complete NASM compatibility.
The fixture records the reference version and executable SHA-256.

Regenerate with `python tests/build_location_fixtures.py --nasm <NASM-3.02-path>`.
Run `python -m unittest discover -s tests`; setting `NASM` to that executable also
replays all captured sources through the live independent oracle. Without it,
the pinned matrix and warning/listing/reuse regressions run in portable CI.

Local Windows verification: 229 methods with NASM enabled, 228 passed and one
optional corpus skipped; portable run: 204 passed and 25 explicit optional
skips. Both complete logs are retained in `PREPROCESSOR_LOCATION_RECEIPT.json.gz`.
