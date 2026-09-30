# NASM roadmap test slice: source inventory and integer boundaries

This slice implements additional parts of `FUTURE_TESTS.md` P0.1 and P0.4.
It does **not** close the instruction-completeness gate. The NASM source is
pinned to `4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065` (3.02).

## Machine-readable source inventory

`tests/fixtures/generated/nasm302_template_ledger.json` records **all 524**
expanded rows tagged `8086`: mnemonic, operand signature, encoding template,
normalized flags, expanded-table line, scope and remaining boundary status.
The table has 337 in-scope integer rows, 162 deferred 8087 rows, 23 excluded
later-width branch rows and two open source32 optimizer aliases (MOVZX/MOVZXD).
None of the excluded/open rows is counted as a passed integer test.

The integer entries contain exact NASM outcomes for O0/O1/O9. Both CPU aliases
are tested, giving 2,022 representative assertions (1,998 accepted-byte checks
and 24 expected optimization-level rejections). The six eligible OPT entries
are no longer invisible. A representative tests source syntax; competing rows
can select the same encoding, so this is not proof that every encoding-template
alternative was selected. Per-row boundary completion deliberately remains open.
The existing FPU corpus is unchanged; no new FPU execution coverage is claimed.

The old raw expanded-file SHA was not reproducible: Perl can emit equivalent
flags as `SM0-1` or separately ordered `SM0,SM1`. The shared inventory parser
normalizes flag sets/ranges and whitespace, then pins all 7,352 table entries
with a semantic SHA-256. Opcode, operand and flag changes remain rejected.
Five independently regenerated Perl hash-seed variants were verified locally.
`stress_templates.py` now checks O1 as well as O0/O9 and fails immediately if
NASM rejects a supposedly legal representative; two rejections cannot pass.

## Boundary matrices

`integer_boundary_cases.py` does not import opcode or mnemonic tables from the
assembler under test. The portable subset has **7,852** accepted source cases:
all register pairs for the ALU/MOV/TEST/XCHG families; all eight based-address
forms and five segment choices; displacement edges; selected unary/shifts;
near/far indirect transfers; direct-address hints; accumulator/group immediate
selection and explicit prefix ordering. Exact O0/O1/O9 binaries are pinned.
Both CPU aliases yield **47,112 instruction-case comparisons** in the portable
suite. The corpus source and each binary have separately checked hashes.

The full opt-in matrix has **35,980** sources. It expands every listed unary
and shift/rotate family across 14 displacement values, all address/segment
choices, byte/word operands and 1/CL counts; it also expands ALU destinations.
Each CPU spelling adds 107,940 O0/O1/O9 comparisons. These are bounded matrices,
not exhaustive combinations of the NASM language.

There are 21 paired CPU/operand negatives. Each tests both the accepted control
and the rejected neighbor. The `[eax]` address case is separate: NASM permits
`67 8b 00` under CPU 8086, but pynasm intentionally rejects it. This is recorded
as a strict-CPU divergence, never a successful byte comparison.

`nasm_reference.py` rejects the wrong reference version, timeouts, crashes,
unexpected exit status and success without an output file. Ordinary diagnostic
rejection is distinct from those harness failures. The new stress runner saves
a failing ASM program, reference/actual bytes and JSON context outside temporary
storage; unexpected reference rejection is always a failure in the legal matrix.

## Commands

From the repository root (set PYTHONPATH to `.` for direct script execution):

```console
python -m unittest discover -s tests
python -m tests.stress_integer_boundaries --nasm /path/to/nasm --cpu 8086
python -m tests.stress_integer_boundaries --nasm /path/to/nasm --cpu 8088
```

Add `--portable` to compare only the smaller pinned corpus. `--batch-size`
changes batching, not coverage. `--failures DIR` selects retained reproducers.

To regenerate the ledger and portable goldens, first run NASM's own expansion
from the pinned NASM checkout, then the generator from the pynasm checkout:

```console
perl -I. x86/preinsns.pl x86/insns.dat expanded-insns.dat
python -m tests.build_roadmap_fixtures --expanded /path/to/expanded-insns.dat --nasm /path/to/nasm
```

The generator uses only NASM as the byte oracle; pynasm does not generate its
own expected bytes. Review generated diffs. Do not replace goldens merely to
make a failing implementation pass. Upstream source-derived template records
retain NASM's license, already included as `doc/NASM_LICENSE`.

## Verified results, 2026-09-30

Local Python 3.13.5/Linux: 159 test methods with live NASM enabled, **158 passed
and one optional independent-corpus test skipped**. Full matrices: **107,940
comparisons per CPU**, no mismatches. The repaired historical template runner:
**1,062 accepted row instances**, no mismatches. Cross-platform CI results are
recorded in the PR rather than implied by these local results.
