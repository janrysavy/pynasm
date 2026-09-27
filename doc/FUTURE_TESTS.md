# Future test implementation roadmap

Updated 2026-09-27. This is the active plan for tests that **still need to be
implemented**. [TESTS.md](TESTS.md) catalogs tests that already exist and how
to run them; [PROGRESS.md](PROGRESS.md) records verified results and open gates.
The older research notes in TESTS.md and [PLAN.md](PLAN.md) explain how the
project began. Do not repeat their completed milestones as new work.

The target remains a pure-Python, fully NASM-compatible 8086/8088 assembler.
The current implementation and most comparisons produce flat binaries. Green
finite test sets establish evidence for their cases, not 100% compatibility.
Per the current priority decision, finish byte-exact instruction and program
behavior first. Listing, debug, map, object-format, and broader CLI tests are
deferred, but remain required before claiming the full target.

## Existing baseline

- The portable suite covers pinned mininasm `input0`/`input1`/`input2`, its
  `xtest` and complete-program fixtures, official NASM regressions, negative
  cases, and three branch-layout programs. Optional live checks use NASM 3.02
  and an independent 19-program corpus.
- Opt-in matrices already cover all 354 selected non-FPU and 162 FPU `8086`
  template representatives, 100,000 selected integer cases for each CPU
  spelling, 9,609 miscellaneous cases for each CPU spelling, and many focused
  expression, prefix, directive, macro, FPU, and layout cases. Their exact
  scopes and commands are in TESTS.md.
- `CPU 8088` is a pynasm alias. NASM 3.02 rejects that spelling, so compare
  our `CPU 8088` output and rejection behavior with NASM's `CPU 8086` target.

## Priority 0: byte-exact 8086/8088 programs

1. **Finish the instruction-template inventory.** Walk the pinned NASM 3.02
   `x86/insns.dat` and its `preinsns.pl` expansion, including 8087 rows.
   Record every applicable template and special selection rule in a machine-
   readable coverage ledger. Extend `stress_insns.py`, `stress_misc_insns.py`,
   `stress_fpu.py`, and `stress_templates.py` beyond representative forms:
   register pairs, all 16-bit addressing forms, displacement and immediate
   boundaries, segment/prefix orders, size and distance qualifiers, and
   competing encodings at `-O0`, `-O1`, and `-O9`. Add rejected operand, CPU,
   and prefix forms alongside accepted bytes. Close this item only when each
   relevant row and selection boundary has an explicit check, rather than
   inferring coverage from the existing 100,000 selected cases.

2. **Expand complete-program layout tests.** Extend
   `stress_program_layout.py` with interacting forward/backward branches,
   `ALIGN`/`ALIGNB`, `TIMES` expressions involving `$` and `$$`, `ORG`,
   sections and `.bss`, local labels, forward `EQU`, `INCBIN`, and mixed
   instruction/data blocks. Check exact output at `-O0`, `-O1`, and `-O9`;
   check convergence and correct rejection for deliberately unstable layouts.
   Preserve each new mismatch as a small source plus pinned NASM golden under
   `tests/fixtures/generated/`. Exercise complete independent and upstream
   programs with both CPU spellings where they stay within the 8086 ISA.

3. **Close expression and relocation boundaries that change bytes.** Build
   focused cases for 64-bit arithmetic/wraparound, forward critical
   expressions, symbol differences, `$`/`$$`, same-section versus cross-section
   references, displacement shrinkage, and range errors. Combine expressions
   with branches, data, and section layout; compare both acceptance and bytes
   with NASM. Keep known NASM 3.02 hang cases out of live batches and document
   each exclusion in TESTS.md.

4. **Verify the CPU boundary systematically.** For every newly covered
   family, pair a legal 8086/8088 form with nearby 186/286/386+ forms that
   must be rejected by this project. NASM 3.02 can emit some later-width
   aliases even under `CPU 8086`; record such deliberate strict-8086
   divergences explicitly rather than treating them as byte-parity successes.

## Priority 1: source needed by real programs

5. **Audit preprocessor interactions, not only isolated directives.** Inventory
   the applicable NASM 3.02 `asm/pptok.dat`, `asm/directiv.dat`, standard
   macros, and `%use` packages. Add complete-program combinations of
   `%include`, `-p`, `-D`, `%define`/`%xdefine`, `%macro`, `%rep`, conditionals,
   contexts, generated labels, file/location built-ins, and source-path rules.
   Compare preprocessed behavior through emitted bytes and rejection. The
   existing focused macro matrices remain regression checks; new tests should
   target uncovered rules and interactions.

6. **Exercise flat-binary API and CLI behavior.** Test default output names,
   `-I`/`-p`/`-D`/`-O` combinations, include search order, file-origin
   built-ins, binary sections, exit codes, and useful diagnostics against the
   pinned profiles. Verify an installed wheel and `python -m pynasm` work
   without a native assembler at runtime. Keep artifact and exit-behavior
   comparisons separate from instruction-byte comparisons.

7. **Extend floating-data and legacy-profile checks where source audits find
   gaps.** Keep the existing 8087 and `FLOAT` matrices green; add cases for
   any untested template or precision edge discovered in NASM source. Expand
   pinned NASM 0.98.39 program goldens so the default legacy profile is not
   judged solely from mininasm-derived examples. Identify version-specific
   encoding choices in each regression.

## Deferred priority: full NASM output surface

8. After the higher-priority gates, create separate golden suites for listing,
   debug and map output, object formats and relocations, and the remaining CLI
   options and diagnostics. Compare artifacts, symbols/relocations, and process
   exit behavior, not just flat-binary bytes. These are open requirements of
   the original full-compatibility goal; flat-binary success cannot close them.
   Yasm may help investigate a disputed rule, but pinned NASM is the byte
   oracle for each named profile.

## Rule for every new matrix

1. Pin the reference version, source revision or fixture, optimization level,
   CPU mode, and any required files or environment. Use deterministic seeds.
2. Check legal input for acceptance and exact bytes; check illegal input for
   rejection. Do not count "both rejected" as success in a legal-input matrix.
3. Batch independent forms for speed, isolate temporary files, and put a
   timeout on live NASM runs. Parallelize independent batches only when measured
   runtime warrants it; preserve a reproducible failing source and seed.
4. On a mismatch, minimize the case, inspect the applicable NASM source rule,
   fix the implementation, add a pinned regression, rerun the affected matrix,
   then run `python -m unittest discover -s tests`. Run larger opt-in matrices
   at milestones rather than on every small edit.
5. Update TESTS.md with the matrix's exact scope and command, and PROGRESS.md
   with the latest verified result. Mark an item closed only when its stated
   source-rule inventory and boundary checks are complete. The full claim
   remains open while any required format or behavior is untested.

Reference pins and runnable commands live in TESTS.md. The current NASM 3.02
source pin is `4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065`; the optional
independent corpus pin is `1979e794d1cbcd92714d0863a2fd17fd89af4fcd`.
