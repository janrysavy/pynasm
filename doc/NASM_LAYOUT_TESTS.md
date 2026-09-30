# Whole-program NASM layout tests (P0.2)

This slice extends `FUTURE_TESTS.md` P0.2 on top of the source-ledger slice.
The oracle remains NASM 3.02 at `4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065`.
No 8087 or later-CPU instruction features are added.

## Additional portable corpus

`tests/fixtures/generated/layout_interactions/` retains readable ASM sources
and a manifest containing independent NASM O0/O1/O9 expected bytes (hex), source
hashes, include-file bytes, seed, and explicit acceptance/rejection categories.
The complete assembled file is compared, not isolated instruction fragments.

There are 24 generated programs across eight families and three origins:

- Code copying an INCBIN payload to aligned BSS, with pointer tables.
- ABSOLUTE record fields, local labels, alignment and location-based fill.
- Physical follows combined with separate virtual addresses and BSS followers.
- Nested includes, macro-local loops, alignment and binary includes.
- Forward EQU lengths crossing sections and reserving matching BSS storage.
- INCBIN ranges and TIMES counts based on `$` and `$$`.
- ALIGNB reservations within initialized sections and cross-section references.
- Forward-resolved fill lengths and branch sizing.

Two minimized late-alignment regressions bring the positive set to **26**.
Both CPU spellings and all three optimization levels give **156 complete-file
byte comparisons**. Six declared rejection cases add **36 rejection checks**:
conflicting ORG, bad section alignment, overlapping sections, unstable TIMES,
code in ABSOLUTE space, and mixed NOBITS placement. The generator verifies every
positive and negative outcome with NASM before writing the manifest. Its unit
test proves that excluded reference hangs are not invoked accidentally.

## New defects found by these tests

### Late alignment could emit the wrong pointer

```nasm
cpu 8086
mov ax,item
section .bss align=16
item: resb 1
alignb 32
```

NASM emits `b8 20 00`; pynasm previously emitted `b8 10 00`. A later alignment
moved section placement but an earlier label had already been bound using the
weaker alignment. Initialized sections were affected too. Repeating a smaller
explicit alignment could also lower an established requirement and cause a
listing-extent failure.

The section-layout calculation now uses the previous pass's final alignment
while binding early labels. Explicit alignment requirements are monotone within
a pass, while a default may still be lowered. Alignment participates in the
convergence state, so it can decrease correctly between relaxation passes.
The regression suite checks symbols, listing addresses, origins, repeated
attributes, reuse, invalid lower values, and a decreasing alignment expression.
This correction applies to both existing compatibility profiles.

The initial regression produced **144 failures and 12 errors**; all pass after
the fix. **63 native NASM assertions** independently verify the byte expectations
and negative controls. The wider program generator found six mismatches in
360 comparisons before this correction; the same cases pass afterward.

### NOBITS mixed physical/virtual placement was silently accepted

NASM forbids combining real `start/align/follows` with virtual
`vstart/valign/vfollows` attributes in NOBITS sections. Pynasm previously emitted
a binary anyway. Attribute tracking now distinguishes defaults from explicit
requirements, including ALIGNB and SECTALIGN even when their value does not
increase. It aggregates repeated declarations and validates the final section
configuration. Tracking resets each pass; diagnostics retain the source site.
The validation rule is applied in the NASM3 profile; the historical profile's
acceptance behavior is unchanged.

The test-first regression produced **199 failures**. **120 native NASM assertions**
verify 99 rejected combinations and 21 accepted controls. Unmixed attributes,
implicit default alignment, SECTALIGN OFF and valid mixed PROGBITS attributes
remain accepted. This is not an implementation of every virtual-alignment form.

## Reference exclusions are not successful comparisons

`cyclic-follows.asm` makes pinned NASM 3.02 time out at O0/O1/O9 under the
five-second reference limit. Its source and exclusion reason are retained in
the manifest. It is never run in the ordinary live corpus and is never counted
as a matched rejection. A separate SUT-only test guards pynasm's prompt cycle
rejection. The five-second timeout is test infrastructure, not an ISA property.

## Commands and retained failures

```console
python -m unittest discover -s tests
python -m tests.stress_program_layout --interactions --count 120 --seed 20260930 --cpu 8086 --nasm /path/to/nasm
python -m tests.stress_program_layout --interactions --count 120 --seed 20260930 --cpu 8088 --nasm /path/to/nasm
python -m tests.build_program_fixtures --nasm /path/to/nasm
```

Without `--interactions`, the existing branch-layout generator is unchanged.
The new mode retains a failing `case.asm`, every input file (including nested
includes), expected/actual bytes when present, and JSON context containing the
seed, optimization level and CPU. Use `--failures DIR` to choose the directory.
A legal program rejected by both assemblers is a failure, not a pass. Ordinary
negative fixtures are separate from reference crashes and timeouts.

## Validation snapshot, 2026-09-30

Python 3.13.5/Linux with live NASM: **173 test methods, 172 passed and one
optional independent-corpus skip**. With native discovery disabled: **153 passed
and 20 optional skips**. New live matrix: **1,440 whole-program comparisons**,
120 programs per seed at O0/O1/O9, both CPU aliases, seeds 20260930 and 8086.
The unchanged branch-only matrix also passes **300 comparisons** (seed 8088).

These are bounded generated families plus minimized regressions, not exhaustive
NASM-language coverage or an execution/emulation test. The remaining roadmap
gates, including complete nonlinear layout and all section attributes, stay open.
