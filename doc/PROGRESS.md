# NASM 8086/8088 compatibility progress

## 2026-09-30 additional verified test slice

[The source-ledger and integer-boundary slice](NASM_ROADMAP_TESTS.md) adds a
524-row inventory and 47,112 portable integer-case comparisons. New opt-in
matrices pass 107,940 comparisons for each CPU alias. Local full suite: 159
methods, 158 passed and one optional corpus skipped. Instruction completeness
remains open; the inventory explicitly retains untested/excluded rows.


Updated 2026-09-27. The target is a pure-Python assembler with full NASM
compatibility for 8086/8088 source. The current implementation emits flat
binaries. NASM 3.02 is the pinned live oracle for the `nasm3` profile;
NASM 0.98.39 encoding choices are the default legacy profile. A green test
suite establishes parity for tested cases, not completion of the full target.

## Current verification snapshot

| Check | Latest verified result | Scope |
|---|---|---|
| `python -m unittest discover -s tests` with `NASM` and `PYNASM_INDEPENDENT_CORPUS` set | 137 passed in 13.0 s | Pinned fixtures, integration tests, optional live NASM checks, independent programs, and three pinned whole-program branch-layout regressions under both CPU spellings |
| `python tests/stress_insns.py --insns INSNS --nasm NASM` | 100,000/100,000 matched | NASM 3.02 selected 8086 integer encoding forms at `-O9` |
| `python tests/stress_insns.py --insns INSNS --nasm NASM --cpu 8088` | 100,000/100,000 matched | Our `CPU 8088` alias against NASM's `CPU 8086` bytes at `-O9` |
| `python tests/stress_misc_insns.py --nasm NASM` | 9,609/9,609 matched | Other 8086 encodings and branch boundaries at `-O0`, `-O1`, and `-O9` |
| `python tests/stress_misc_insns.py --nasm NASM --cpu 8088` | 9,609/9,609 matched | Same matrix with our `CPU 8088` alias against NASM's `CPU 8086` bytes |
| `python tests/stress_program_layout.py --nasm NASM --count 100 --seed 8088` | 300/300 matched | Randomized complete programs with interacting branches, alignment, and data at `-O0`, `-O1`, and `-O9` |
| `python tests/stress_program_layout.py --nasm NASM --count 200 --seed 42` | 600/600 matched | A second deterministic program-layout seed |
| `python tests/stress_program_layout.py --nasm NASM --count 200 --seed 123` | 600/600 matched | A third deterministic program-layout seed |
| `python tests/stress_program_layout.py --nasm NASM --count 100 --cpu 8088` | 300/300 matched | Complete-program layout with our 8088 alias against NASM's 8086 bytes |
| `python tests/stress_branch_qualifiers.py --nasm NASM` | 1,944/1,944 matched | Branch width and distance qualifiers after the layout fix |
| `python tests/stress_default_bnd.py --nasm NASM` | 189/189 matched | Default and explicit BND/NOBND transfer encodings and branch boundaries |
| `python tests/stress_global_directives.py --nasm NASM` | 64/64 matched | Flat-binary acceptance/rejection of global directives |
| `python tests/stress_pp_macro_depth.py --nasm NASM` | 34/34 matched | Acyclic single-line macro chains through 4,096 links at `-O0` and `-O9` |
| `python tests/stress_pp_smacro_recursion.py --nasm NASM` | 20/20 matched | Direct and mutual single-line recursion guard cases |
| `python tests/stress_pp_control_flow.py --nasm NASM` | 36/36 matched | `%rep`, `%exitrep`, `%exitmacro`, and `%rotate` cases at `-O0` and `-O9` |
| `python tests/stress_dollarhex.py --nasm NASM` | 44/44 matched | Bracketed `DOLLARHEX` switching, `$`-prefixed literals/symbols, and preprocessor use at `-O0` and `-O9` |
| `python tests/stress_float_options.py --nasm NASM` | 76/76 matched | `FLOAT` rounding switches, DAZ, status macros, float functions, and former precision-edge inputs at `-O0` and `-O9` |
| `python tests/stress_float_precision.py --nasm NASM` | 8,568/8,568 matched | Decimal and binary-radix data across six widths, six option modes, and `-O0`/`-O9`, including long significands and exponent extremes |
| `python tests/stress_data_directives.py --nasm NASM` | 628/628 matched | Data, reserve, DUP, TIMES, and alignment cases at `-O0` and `-O9` |

The full catalog of pinned and generated test matrices, including the
100,000-case selected integer-encoding stress runner, is in [TESTS.md](TESTS.md).
Those larger runners are separate from the 137-test suite and are **not**
implied by its green result. NASM 3.02 rejects `CPU 8088`; its `CPU 8086`
target is the oracle for our 8088 alias. The 9,999-link macro case is excluded from the
live matrix because the pinned NASM 3.02 process overflows its stack on it.

## Workstream gates

`Covered` means tested examples pass. `Open` means the completion gate has
not been met. A workstream stays open if its tests cover only representative
forms or if a known feature is missing.

| Workstream | Status | Evidence now | Gate to close |
|---|---|---|---|
| Pure-Python API and flat-binary CLI | Covered | `pynasm.assemble`, CLI, and complete program fixtures run without a native runtime dependency | Keep the API/CLI checks green through final verification |
| 8086/8088 integer and 8087 encoding | Open | Pinned mininasm corpus; 354 non-FPU and 162 FPU NASM `8086` template representatives; generated operand matrices | Audit every relevant NASM template and selection rule, then exercise operand, prefix, address, optimization, and rejection boundaries with zero known mismatches |
| Expressions, symbols, and binary layout | Open | Pinned program fixtures and expression, branch, section, data, include, and alignment matrices | Finish source-rule audit for forward references, section behavior, critical expressions, and all flat-binary directives; add regressions for every discrepancy |
| Floating-point option parity | Covered | The former 14 mismatches now match; 76 option and 8,568 precision comparisons pass | Keep these matrices green while broader floating-point syntax remains under the expressions/layout audit |
| Preprocessor and macro language | Open | Official NASM macro regressions and focused differential matrices listed in TESTS.md; latest depth, recursion, and control-flow runs pass | Inventory NASM 3.02 preprocessor tokens/directives and interactions; close each missing or mismatching behavior with a source-backed rule and regression |
| Full NASM command-line/output compatibility | Open | CLI currently accepts only `-f bin`; NASM object formats, listing output, and full diagnostics/option behavior are not implemented | Decide and implement the remaining NASM 8086 output and CLI surface required by the full compatibility target, then compare generated artifacts and exit behavior |
| End-to-end compatibility claim | Open | Pinned NASM fixtures, independent programs, and live differential runners exercise substantial but finite subsets | Run all required suites against pinned references, resolve every known mismatch, and review the feature/format inventory against NASM source; do not infer 100% from a finite green sample |

## Current priority and deferred work

The immediate priority is byte-exact 8086/8088 instruction encoding, complete
program behavior, branch layout, and expressions or preprocessor features that
block those programs. The selected 100,000-case matrix passes for both CPU
spellings, but it does not cover every form or interaction in NASM's source.
The new whole-program differential found and fixed a forward-Jcc relaxation
error: a preceding pass could leave a branch wide when its short form fits,
or oscillate between short and wide around intervening `ALIGN` padding and
branches. Three pinned NASM 3.02 binary fixtures now guard those cases.

Listing, debug, map, object-format output, and broader CLI parity are deferred
at the user's direction. They remain open against the original full-compatibility
goal. The recently audited flat-binary `DEFAULT`, `LIST`, `DEBUG`, symbol, and
label-mangling directives pass their focused matrices; this does not imply that
their non-binary effects are implemented.

## Next sequence

Use [FUTURE_TESTS.md](FUTURE_TESTS.md) as the active implementation sequence
for the open test gates above. It keeps high-priority byte and program work
ahead of deferred output formats and defines how to add and verify each matrix.

## Reproducing the snapshot

From the repository root, point `NASM` at NASM 3.02 and
`PYNASM_INDEPENDENT_CORPUS` at the pinned independent checkout, then run:

```console
python -m unittest discover -s tests
python tests/stress_insns.py --insns path/to/insns.dat --nasm path/to/nasm
python tests/stress_insns.py --insns path/to/insns.dat --nasm path/to/nasm --cpu 8088
python tests/stress_misc_insns.py --nasm path/to/nasm
python tests/stress_misc_insns.py --nasm path/to/nasm --cpu 8088
python tests/stress_program_layout.py --nasm path/to/nasm --count 100 --seed 8088
python tests/stress_program_layout.py --nasm path/to/nasm --count 200 --seed 42
python tests/stress_program_layout.py --nasm path/to/nasm --count 200 --seed 123
python tests/stress_program_layout.py --nasm path/to/nasm --count 100 --cpu 8088
python tests/stress_branch_qualifiers.py --nasm path/to/nasm
python tests/stress_default_bnd.py --nasm path/to/nasm
python tests/stress_global_directives.py --nasm path/to/nasm
python tests/stress_pp_macro_depth.py --nasm path/to/nasm
python tests/stress_pp_smacro_recursion.py --nasm path/to/nasm
python tests/stress_pp_control_flow.py --nasm path/to/nasm
python tests/stress_dollarhex.py --nasm path/to/nasm
python tests/stress_float_options.py --nasm path/to/nasm
python tests/stress_float_precision.py --nasm path/to/nasm
```

See [TESTS.md](TESTS.md) for the other opt-in stress commands and reference
commit IDs.
