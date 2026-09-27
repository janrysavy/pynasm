# 8086/8088 assembler test plan and status

The active plan for **tests still to implement** is in
[FUTURE_TESTS.md](FUTURE_TESTS.md). This file catalogs existing checks,
run commands, source findings, and historical research notes.

The runnable suite now covers these four properties: accepted 8086 source,
byte-for-byte encoding against pinned goldens or NASM, rejection of malformed
input, and rejection of post-8086 instructions under `cpu 8086`. The tests are
evidence for the exercised cases, not a proof of complete NASM compatibility.

| Layer | Implementation | Reference |
|---|---|---|
| mininasm encoding and programs | `tests/test_mininasm_corpus.py` | Pinned sources and binaries in `tests/fixtures/mininasm/` |
| mininasm nested include integration | `tests/test_mininasm_corpus.py` | Upstream `test/INCLUDE.ASM` and three nested include files against its 24-byte `INCLUDE.COM` golden |
| Unstable label layout | `tests/test_external_corpora.py` | mininasm `test/unstable.nasm`; `REP=66` fails at `-O9`, `REP=65` assembles |
| NASM official 8086 regressions | `tests/test_external_corpora.py` | NASM 3.02 `travis/test/andbyte`, `bcd`, `bintest`, `br2003451`, `br3026808`, `float`, `float8`, `floatx`, `floatize`, `hexfp`, `ifid`, `ifmacro`, `iftoken`, `ilog`, `radix`, `warnstack`, `xdefine`, and `br3028880` sources and upstream goldens; `floatb` with only `BITS 64` changed to `CPU 8086`/`BITS 16`, retaining its upstream golden; binary `nasmformat` with a NASM 3.02 golden; path-dependent `_file_` and timestamp-dependent `time` compared live |
| Object-attribute syntax under flat binary | `tests/test_external_corpora.py` | Official NASM 3.02 `alonesym-obj` and `winalign` sources with binary goldens regenerated using `-f bin -O0`; checks ignored object attributes and `SECTALIGN` |
| DOS EXE macro integration | `tests/test_external_corpora.py` | NASM 3.02 `travis/test/binexe.asm` and `misc/exebin.mac`, assembled as a flat binary against a pinned 63-byte NASM golden |
| Include and preinclude integration | `tests/test_external_corpora.py` | Official `br890790` include-inside-`%rep` and `inctest` nested includes with `-p inc3.asm`; API and CLI outputs checked against upstream binaries |
| Independent hand-written programs | `tests/test_external_corpora.py` | All 19 `j-helland/8086-disassembler/asm` sources, compared to NASM 3.02 at `-O0`, `-O1`, and `-O9`, including our `CPU 8088` alias |
| Generated routine differential | `tests/test_differential.py` | Thousands of forms and boundaries compared to installed NASM, including 210 forward/backward 32-bit branch cases at `-O0`, `-O1`, and `-O9` |
| Expression operators and precedence | `tests/test_expression_corpus.py` | NASM 3.02 golden for ternary, boolean XOR, comparisons, shifts, and mixed precedence |
| Dollar-hex directive and token stress | `tests/stress_dollarhex.py` | 44 default/on/off, boolean-option, `$`-prefixed symbol and literal, preprocessor-expression, and bare-directive comparisons at `-O0` and `-O9` against NASM 3.02 |
| Default-BND transfer stress | `tests/stress_default_bnd.py` | 189 `DEFAULT`/`BND`/`NOBND` near/far jump, call, return, Jcc, prefix, option, and boundary comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Global-directive flat-binary stress | `tests/stress_global_directives.py` | 64 `LIST`, `DEBUG`, symbol declaration, and label-mangling acceptance/rejection comparisons at `-O0` and `-O9` against NASM 3.02 |
| Floating-point option stress | `tests/stress_float_options.py` | 76 `FLOAT` near/down/up/zero, DAZ, reset, bare macro, status-macro, float-function, and former decimal-precision-boundary comparisons at `-O0` and `-O9` against NASM 3.02 |
| Floating-point precision stress | `tests/stress_float_precision.py` | 8,568 decimal and binary-radix literals across all six data widths, six `FLOAT` modes, and `-O0`/`-O9`, including 52/53/70-digit significands and exponent extremes, against NASM 3.02 |
| Generated expression stress | `tests/stress_expressions.py` | 3,974 64-bit operand/operator combinations compared to NASM 3.02 in small batches |
| Generated encoding stress | `tests/stress_insns.py` | 100,000 selected 8086 arithmetic/data-move forms derived from pinned NASM `insns.dat`, compared to NASM 3.02; a second 100,000-case run checks our `CPU 8088` alias against the same NASM bytes |
| Expanded NASM 8086 templates | `tests/test_insns_corpus.py`, `tests/stress_templates.py` | A pinned flat-binary corpus and live comparisons for one representative source form from each of 354 NASM 3.02 non-FPU, non-APX, non-OPT rows tagged `8086`, at `-O0` and `-O9`; includes 32-bit branch-target templates and ECX/RCX shift-count aliases |
| Other 8086/8088 encoding and branch stress | `tests/stress_misc_insns.py` | 9,609 stack, unary, shift, segment, far-transfer, I/O, return, and branch cases at `-O0`, `-O1`, and `-O9` against NASM 3.02 for each of our `CPU 8086` and `CPU 8088` spellings; includes chained boundary branches and all data widths on LEA memory operands |
| Interacting whole-program branch layout | `tests/stress_program_layout.py`, `tests/test_external_corpora.py` | 500 deterministic complete programs (1,500 comparisons) across three seeds and `-O0`/`-O1`/`-O9`, plus 100 programs (300 comparisons) with our `CPU 8088` alias; three NASM 3.02 golden programs pin forward-Jcc shortening, alignment-sensitive branch sizing, and branch convergence |
| Branch qualifier stress | `tests/stress_branch_qualifiers.py` | 1,944 accepted/rejected numeric and current-address `byte`/`word`/`dword`, `short`/`near` combinations at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Combined qualifier stress | `tests/stress_qualifier_sequences.py` | 864 accepted/rejected mixed operand size, distance, and `strict` qualifier sequences at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Address qualifier stress | `tests/stress_address_qualifiers.py` | 1,470 memory-bracket displacement-width, direct-address, segment, address-size hint/prefix, prefix-order, and LOOP/JCXZ counter-form comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Data-directive stress | `tests/stress_data_directives.py` | 628 numeric, string, per-item size override, grouped expression, `DUP`, reserve, `TIMES`, alignment, and label comparisons at `-O0` and `-O9` against NASM 3.02; includes all NASM `RES*` widths and `DY`/`DZ` |
| Binary-include stress | `tests/stress_incbin.py` | 140 `INCBIN` range, quoting, `TIMES`, malformed-operand, and EOF comparisons at `-O0` and `-O9` against NASM 3.02 |
| Source-include stress | `tests/stress_includes.py` | 46 `%include`, `%require`, `%depend`, and `%pathsearch` quoting, macro expansion, nested file, malformed operand, and search-order comparisons at `-O0` and `-O9` against NASM 3.02 |
| File-condition stress | `tests/stress_pp_file_conditions.py` | 76 `%iffile`/`%ifnfile`/`%eliffile`/`%elifnfile` exact-path, quoting, macro, and malformed-operand comparisons at `-O0` and `-O9` against NASM 3.02 |
| Directive-condition stress | `tests/stress_pp_directive_conditions.py` | 1,290 `%ifdirective`/`%ifndirective` and `%elif*` checks spanning pinned `directiv.dat` names, all generated `%if`/`%elif` names from `pptok.dat`, quoting, and unknown names against NASM 3.02 |
| Package-condition stress | `tests/stress_pp_package_conditions.py` | 1,024 `%ifusable`/`%ifusing` and `%elif*` checks for available, unknown, and loaded `%use` packages, including quoted and malformed names, against NASM 3.02 |
| Alternate-register package stress | `tests/stress_altreg.py` | 260 `%use altreg` checks covering every declared alias, representative 8086 MOV encodings, package markers, and repeat-load behavior against NASM 3.02 |
| Smart-alignment package stress | `tests/stress_smartalign.py` | 1,004 `%use smartalign` 16-bit padding, jump-threshold, mode-transition, origin, status-macro, and explicit-fill comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| MASM and vtern package stress | `tests/stress_masm.py` | 156 `%use masm`/`%use vtern` acceptance and binary comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02; covers 16-bit MASM procedure, section, `PTR`, `OFFSET`, `TBYTE`, and x87 aliases |
| Standard section/alignment macro stress | `tests/stress_standard_macros.py` | 311 section-status, alignment-switch, `ORG`, `ALIGN`, `ALIGNB`, and invalid-boundary comparisons against NASM 3.02 |
| Absolute-space and structure stress | `tests/stress_absolute.py`, `tests/stress_structures.py` | 63 `ABSOLUTE`/reservation and 54 `STRUC`/`ISTRUC`/`AT`/`IEND` comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Preprocessor alias stress | `tests/stress_pp_aliases.py` | 105 `%defalias`/`%idefalias`, `%undefalias`, alias-chain, redefine, `%ifdefalias`, and `%aliases on/off` comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Reserved macro alias stress | `tests/stress_pp_rmacro.py` | 38 `%rmacro`/`%irmacro` and exact-spelling `%ifmacro`/`%ifdef` comparisons at `-O0` and `-O9` against NASM 3.02 |
| Reserved TASM conditional stress | `tests/stress_pp_difi.py` | 20 `%ifdifi`/`%ifndifi` and `%elif*` comparisons at `-O0` and `-O9`; NASM suppresses all later branches of this stub condition |
| Conditional identifier-list stress | `tests/stress_pp_multi_conditions.py` | 36 `%ifdef`, `%ifdefalias`, `%ifctx`, `%ifenv`, and negated/`%elif*` comparisons at `-O0` and `-O9`, including case-insensitive context names and macro-expanded environment names |
| Token-identity conditional stress | `tests/stress_pp_idn.py` | 40 `%ifidn`, `%ifidni`, and negated/`%elif*` token comparisons at `-O0` and `-O9`, including mixed string quote styles, whitespace, macro expansion, and extra commas |
| Token-type conditional stress | `tests/stress_pp_types.py` | 60 `%ifid`, `%ifnum`, `%ifstr`, `%iftoken`, `%ifempty`, and negated/`%elif*` comparisons at `-O0` and `-O9`, including repeated numeric sign tokens |
| Multiline-macro conditional stress | `tests/stress_pp_ifmacro.py` | 46 `%ifmacro`/`%ifnmacro` name, count-range, missing-macro, and trailing-token comparisons at `-O0` and `-O9` against NASM 3.02 |
| Multiline-macro removal stress | `tests/stress_pp_unmacro.py` | 36 `%unmacro`/`%unimacro` signature, greedy `+`, malformed-name, and count-range comparisons at `-O0` and `-O9` against NASM 3.02 |
| Preprocessor pragma stress | `tests/stress_pp_pragma.py` | 38 flat-binary `%pragma` comparisons at `-O0` and `-O9`, including macro-expanded namespace, unknown options, and the `preproc sane_empty_expansion` effect on empty macro arguments; a namespace-only `%pragma bluttan` case is excluded because the pinned NASM binary stalls on it |
| Multiline-macro overload stress | `tests/stress_pp_macro_overloads.py` | 34 same-name multiline macro definition, overload-selection, redefine-order, greedy `+`, `%ifmacro`, `%unmacro`, and case-sensitivity comparisons at `-O0` and `-O9` against NASM 3.02 |
| Multiline-macro argument stress | `tests/stress_pp_macro_args.py` | 62 brace-only grouping, commas inside parentheses/brackets, braced defaults, terminal-empty-argument, legacy fallback, and `sane_empty_expansion` comparisons at `-O0` and `-O9` against NASM 3.02 |
| Multiline-macro reference stress | `tests/stress_pp_macro_refs.py` | 42 `%{first:last}` forward/reverse/negative/rotated range, `%?`/`%??` name, invalid-range, and quoted-literal comparisons at `-O0` and `-O9` against NASM 3.02 |
| Multiline-macro condition-code stress | `tests/stress_pp_macro_cc.py` | 86 `%+n`/`%-n` condition-code validation, inverse, rotation, case, quoted-literal, and invalid-operand comparisons at `-O0` and `-O9` against NASM 3.02 |
| Macro indirection stress | `tests/stress_pp_indirection.py` | 60 `%[...]` expansion, nesting, token concatenation, eager `%define` body, multiline macro, dynamic name, directive, quoted-literal, and comment comparisons at `-O0` and `-O9` against NASM 3.02 |
| Single-line macro name stress | `tests/stress_pp_selfrefs.py` | 28 `%?`, `%??`, `%*?`, and `%*??` invoked/declared-name comparisons in case-sensitive and case-insensitive plain and parameterized macros, including definitions inside multiline macros, at `-O0` and `-O9` against NASM 3.02 |
| Greedy single-line macro stress | `tests/stress_pp_greedy_smacro.py` | 54 `+` final-parameter, optional-empty, brace grouping, square-bracket splitting, and `%,` conditional-comma comparisons at `-O0` and `-O9` against NASM 3.02 |
| Single-line macro parameter-flag stress | `tests/stress_pp_smacro_flags.py` | 60 `=` numeric evaluation and radix, `&`/`&&` string conversion, `!` whitespace preservation, and unnamed-parameter comparisons at `-O0` and `-O9` against NASM 3.02 |
| Single-line macro overload stress | `tests/stress_pp_smacro_overloads.py` | 48 arity, redefinition, greedy/fixed precedence, case sensitivity, `%undef`, declared-name, and parameterless-conflict comparisons at `-O0` and `-O9` against NASM 3.02 |
| Single-line macro recursion stress | `tests/stress_pp_smacro_recursion.py` | 20 direct, mutual, nested, case-insensitive, and independent-call recursion-guard comparisons at `-O0` and `-O9` against NASM 3.02 |
| Single-line macro depth stress | `tests/stress_pp_macro_depth.py` | 34 acyclic macro-chain comparisons from 1 through 4,096 links at `-O0` and `-O9` against NASM 3.02; the pinned NASM binary overflows its stack at 9,999 links |
| Preprocessor control-flow stress | `tests/stress_pp_control_flow.py` | 36 `%rep`, `%exitrep`, `%exitmacro`, and `%rotate` comparisons, including nested repetitions and inactive branches, at `-O0` and `-O9` against NASM 3.02 |
| Braced preprocessor-token stress | `tests/stress_pp_braced_tokens.py` | 24 `%{...}` local-label, condition-code, macro-name, context-local, directive, empty-modulo, and quoted-literal comparisons at `-O0` and `-O9` against NASM 3.02 |
| Conditional expression stress | `tests/stress_pp_if_expr.py` | 50 `%if`/`%elif`/`%ifn`/`%elifn` expression comparisons at `-O0` and `-O9`, including NASM's warning-only trailing tokens and malformed expressions that must still fail |
| Preprocessor clearing stress | `tests/stress_pp_clear.py` | 64 `%clear` definition, alias, macro, option, context-scope, and built-in macro lifecycle comparisons at `-O0` and `-O9` against NASM 3.02 |
| Source-location stress | `tests/stress_pp_line.py` | 66 `%line`/`#` marker, line-increment, virtual filename, macro-body, repetition, and nested-include comparisons at `-O0` and `-O9` against NASM 3.02 |
| TASM-style stack directive stress | `tests/stress_pp_stack.py` | 88 `%stacksize`, `%arg`, and `%local` cases at `-O0` and `-O9`; 80 compare bytes/rejection with NASM 3.02, and eight assert strict rejection of NASM-permitted EBP addressing that an 8086 cannot execute |
| Preprocessor string/token stress | `tests/stress_pp_strings.py` | 750 `%strcat`, `%strlen`, `%substr`, `%deftok`, `%defstr`, and case-insensitive variant comparisons against NASM 3.02; includes a 576-case substring-boundary matrix |
| Operand-size prefix stress | `tests/stress_operand_size_prefixes.py` | 858 accepted/rejected `o16`/`o32` cases across 8086 integer, branch, memory, and FPU forms at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Effective-address expression stress | `tests/stress_effective_address_syntax.py` | 714 register-arithmetic, cancellation, scale, displacement-before-bracket, label, and numeric-expression comparisons at `-O0`, `-O1`, and `-O9` against NASM 3.02 |
| Explicit prefix stress | `tests/stress_prefixes.py` | 1,048 accepted/rejected prefix ordering, duplicate/conflicting-prefix, segment-override, and prefixed-label branch comparisons against NASM 3.02, including `REPNE` conditional jumps and near returns |
| Mixed operand acceptance and bytes | `tests/stress_operand_validation.py` | 3,860 deterministic valid/invalid operand and qualifier samples at each of `-O0`, `-O1`, and `-O9` against NASM 3.02 (11,580 comparisons) |
| 8087 templates and stress | `tests/test_fpu_corpus.py`, `tests/stress_fpu.py` | All 162 NASM 3.02 `8086,FPU` rows against a pinned binary; 22,024 additional register/address/optimization comparisons against live NASM |

Run portable pinned tests with `python -m unittest discover -s tests`. Set
`NASM` to a NASM 3.02 executable to enable the live differential tests. The
independent suite also needs `PYNASM_INDEPENDENT_CORPUS` set to a checkout of
`j-helland/8086-disassembler` at commit
`1979e794d1cbcd92714d0863a2fd17fd89af4fcd`; its source is not bundled.

To run the large matrix from the repository root:

```console
python -m tests.stress_insns --insns path/to/nasm-3.02/x86/insns.dat --nasm path/to/nasm
python -m tests.stress_insns --insns path/to/nasm-3.02/x86/insns.dat --nasm path/to/nasm --cpu 8088
python -m tests.stress_templates --expanded path/to/expanded-insns.dat --nasm path/to/nasm
python -m tests.stress_misc_insns --nasm path/to/nasm
python -m tests.stress_misc_insns --nasm path/to/nasm --cpu 8088
python -m tests.stress_program_layout --nasm path/to/nasm --count 100 --seed 8088
python -m tests.stress_program_layout --nasm path/to/nasm --count 200 --seed 42
python -m tests.stress_program_layout --nasm path/to/nasm --count 200 --seed 123
python -m tests.stress_program_layout --nasm path/to/nasm --count 100 --cpu 8088
python -m tests.stress_branch_qualifiers --nasm path/to/nasm
python -m tests.stress_qualifier_sequences --nasm path/to/nasm
python -m tests.stress_address_qualifiers --nasm path/to/nasm
python -m tests.stress_data_directives --nasm path/to/nasm
python -m tests.stress_incbin --nasm path/to/nasm
python -m tests.stress_includes --nasm path/to/nasm
python -m tests.stress_pp_file_conditions --nasm path/to/nasm
python -m tests.stress_pp_directive_conditions --nasm path/to/nasm
python -m tests.stress_pp_package_conditions --nasm path/to/nasm
python -m tests.stress_altreg --nasm path/to/nasm
python -m tests.stress_smartalign --nasm path/to/nasm
python -m tests.stress_masm --nasm path/to/nasm
python -m tests.stress_standard_macros --nasm path/to/nasm
python -m tests.stress_absolute --nasm path/to/nasm
python -m tests.stress_structures --nasm path/to/nasm
python -m tests.stress_pp_aliases --nasm path/to/nasm
python -m tests.stress_pp_rmacro --nasm path/to/nasm
python -m tests.stress_pp_difi --nasm path/to/nasm
python -m tests.stress_pp_multi_conditions --nasm path/to/nasm
python -m tests.stress_pp_idn --nasm path/to/nasm
python -m tests.stress_pp_types --nasm path/to/nasm
python -m tests.stress_pp_ifmacro --nasm path/to/nasm
python -m tests.stress_pp_unmacro --nasm path/to/nasm
python -m tests.stress_pp_pragma --nasm path/to/nasm
python -m tests.stress_pp_macro_overloads --nasm path/to/nasm
python -m tests.stress_pp_macro_args --nasm path/to/nasm
python -m tests.stress_pp_macro_refs --nasm path/to/nasm
python -m tests.stress_pp_macro_cc --nasm path/to/nasm
python -m tests.stress_pp_indirection --nasm path/to/nasm
python -m tests.stress_pp_selfrefs --nasm path/to/nasm
python -m tests.stress_pp_greedy_smacro --nasm path/to/nasm
python -m tests.stress_pp_smacro_flags --nasm path/to/nasm
python -m tests.stress_pp_smacro_overloads --nasm path/to/nasm
python -m tests.stress_pp_smacro_recursion --nasm path/to/nasm
python -m tests.stress_pp_macro_depth --nasm path/to/nasm
python -m tests.stress_pp_control_flow --nasm path/to/nasm
python -m tests.stress_pp_braced_tokens --nasm path/to/nasm
python -m tests.stress_pp_if_expr --nasm path/to/nasm
python -m tests.stress_pp_clear --nasm path/to/nasm
python -m tests.stress_pp_line --nasm path/to/nasm
python -m tests.stress_pp_stack --nasm path/to/nasm
python -m tests.stress_pp_strings --nasm path/to/nasm
python -m tests.stress_operand_size_prefixes --nasm path/to/nasm
python -m tests.stress_effective_address_syntax --nasm path/to/nasm
python -m tests.stress_prefixes --nasm path/to/nasm
python -m tests.stress_operand_validation --nasm path/to/nasm
python -m tests.stress_expressions --nasm path/to/nasm
python -m tests.stress_dollarhex --nasm path/to/nasm
python -m tests.stress_default_bnd --nasm path/to/nasm
python -m tests.stress_global_directives --nasm path/to/nasm
python -m tests.stress_float_options --nasm path/to/nasm
python -m tests.stress_float_precision --nasm path/to/nasm
python -m tests.stress_fpu --nasm path/to/nasm
```

The expression stress runner omits signed `INT64_MIN / -1` and modulo by `-1`:
the pinned NASM 3.02 reference stalls on those inputs. All other generated
cases use a five-second per-batch timeout.

The stress script checks `insns.dat` SHA-256
`34c98c66fb85e08655823f1fb8e267ca61af5b172e97f2220efedc7ac8f81571`
from NASM commit `4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065`. It
enumerates selected `8086` memory/register forms, displacement boundaries,
and segment overrides. Generate the expanded table for `stress_templates.py`
from that commit with `perl -I. x86/preinsns.pl x86/insns.dat expanded-insns.dat`
in the NASM source root. The template corpus instantiates every filtered row
once; it does not prove every operand combination or that each NASM encoding
template was selected by its representative source. The official fixture
sources and binaries use NASM's BSD-2
license in `doc/NASM_LICENSE`; the mininasm fixtures use `doc/MININASM_LICENSE`.

The operand-validation fixes were checked against that pinned source:
`asm/parser.c` rejects `FAR` on non-memory operands except `JMP`/`CALL`;
`x86/insns.dat` gives LEA an unsized `mem` operand and separates 8086 and
later-width templates; `x86/preinsns.pl` expands the 8086 shift templates to
`unity`, `reg_cl`, and the undocumented `reg_cx` alias. Conditional-branch
selection follows the short/near and jump-over templates in `x86/insns.dat`
and `asm/assemble.c`.
NASM's `include/nasm.h` sets `OPTIM_STRICT_OPER` at `-O0` but not `-O1`;
`asm/parser.c` uses that flag when assigning the `unity` operand class.
The `DOLLARHEX` switch follows `asm/directiv.c` and `asm/getbool.c`;
`asm/stdscan.c` recognizes a `$`-prefixed hex number only when the character
after `$` is a digit, while `nasmlib/readnum.c` checks whether dollar-hex mode
is enabled. Thus `$ff` remains a symbol even with the default mode on.
`asm/floats.c` defines `FLOAT` rounding and DAZ options and converts decimal
literals through a 192-bit intermediate mantissa. Its directed-rounding helper
adds at the first discarded bit, so a directed round-up does not change the
emitted field when that bit is clear; the Python encoder now follows this
behavior.
The `DEFAULT BND` cases follow `asm/directiv.c`, the `IF_BND` rows in
`x86/insns.dat`, and the prefix/template selection checks in `asm/assemble.c`.
The source marks near CALL/JMP/RET and short Jcc forms as BND-capable; a
relaxed short JMP drops a default BND prefix, while explicit BND/NOBND keeps
the near JMP template. `LIST`, `DEBUG`, declarations, and label mangling follow
`asm/directiv.c` and are checked here only for flat-binary bytes/rejection.
It also keeps the first operand size word when multiple appear; its distance
flags can coexist, so `short` takes precedence over `near` for JMP/Jcc
template selection. `strict` prevents branch relaxation.
Inside memory brackets, `byte` and `word` select displacement encoding, not
operand width. `dword` permits a direct 32-bit address with NASM's `67h`
address-size prefix even under `CPU 8086`.
The bracket hints `a16`, `a32`, `abs`, `rel`, and `nosplit` follow NASM's
16-bit address rules; instruction-level `a16`/`a32` prefixes share the same
address-size constraint and canonical prefix order.
Instruction-level `o16`/`o32` prefixes use NASM's operand-size slot. A written
32-bit relative JMP/CALL target can retain its 32-bit displacement with `o16`
suppressing `66h`; FPU's automatic `WAIT` precedes an explicit `o32` prefix.
NASM reduces effective addresses as linear register expressions before
selecting ModR/M; zero coefficients vanish and coefficients simplified to one
become ordinary 8086 base/index registers.
The parser also accepts `displacement[register]`. Relocatable label offsets
retain a full word displacement; relocation-free differences such as
`target-$$` can shrink to a byte after resolution.
For data directives, NASM's `asm/parser.c` permits element-size overrides and
grouped expression lists within `DB`/`DW`/`DD`/`DQ`. The NASM 3 profile now
matches the sampled per-item and `DUP` encodings, including its treatment of
negative `RES*` counts as zero-length reservations.
`INCBIN` follows the parser's one-filename/two-range operand limit. NASM 3
looks for relative binary filenames in the working directory and configured
include paths; `%include` uses the same path order and requires a quoted name.
`-p` preincludes use that order too. The legacy profile retains source-relative
lookup.
NASM's `%iffile` and `%ifnfile` probe the exact path in the working directory;
they do not search `-I` directories. The `%eliffile` variants have the same
lookup behavior.
`%ifdirective` follows NASM's pinned `asm/directiv.dat` and `asm/pptok.dat`
tables. The flat-binary backend recognizes `ORG` and `MAP` but not unrelated
format directives such as `EXPORT`.
The package conditions follow the six `USE:` records in NASM's `macros/*.mac`;
`standard.mac` is part of NASM's standard macros but is not a `%use` package.
The 16-bit smart-alignment modes follow NASM's `macros/smartalign.mac`.
Its `k7` branch updates the first four patterns without changing the previous
16-bit group size, so mode transitions retain that state.
Under a misaligned `ORG`, `SECTALIGN` advances the initial `.text` file start;
the implicit `.text` section otherwise has byte alignment.
NASM's standard `ALIGN` and `ALIGNB` macros calculate padding from `$-$$`.
`SECTALIGN off` disables their section-alignment update but does not change that
padding calculation; non-power-of-two boundaries then remain usable. The
smartalign package's replacement `ALIGN` macro calls
`SECTALIGN` even when the standard macro switch is off. The standard
`__?SECT?__`/`__SECT__` and section-alignment status aliases are exposed to
preprocessing.
`ABSOLUTE` advances labels through reserve directives without contributing
bytes to flat-binary output. The standard structure macros build on that
address space; `ISTRUC` uses the resulting offsets to emit instance padding.
Single-line preprocessor aliases follow their target when expanded, defined,
or undefined. `%undefalias` removes the alias link. Legacy built-in names such
as `__BITS__` are aliases of their `__?BITS?__` forms and obey `%aliases off`.
The pinned NASM 3.02 executable stalls on a probe that combines `%aliases off`
and `%ifdef` of a disabled alias; that probe is excluded from the live matrix.
String directives expand their operands before processing. `%substr` uses
one-based indices, clamps out-of-range starts, and interprets negative counts
relative to the string end; `%deftok` turns quoted contents back into source
tokens.
`macros/masm.mac` provides a limited MASM compatibility package. Under
`CPU 8086`, the implemented package rules cover its procedure, segment,
and operand aliases; `vtern` is loadable and exposes its macro declarations,
while its vector instructions remain unavailable under that CPU.
`asm/parser.c` stores explicit instruction prefixes by slot and rejects
conflicting entries; `asm/assemble.c` emits them in slot order. The NASM 3
profile follows that order and counts prefix bytes in relative branch sizes.
`REPNE`/`REPNZ` on a conditional jump selects NASM's jump-over-near template
even when the source requests a short jump; `LOOP` and `JCXZ` stay short.
NASM rejects those prefixes on near `JMP`, `CALL`, `RET`, and `RETN` forms
marked `BND` in `x86/insns.dat`.
The pinned NASM 0.98.39 corpus keeps its original prefix-order behavior.

Yasm remains a possible supplemental oracle; no Yasm check is required by the
current suite. All filtered 8086 rows now have representative source forms,
while exhaustive operand and encoding-choice coverage remains open.

The notes below document the source selection and longer-term coverage goals.

---

## Research notes

Several useful upstream suites informed this test stack.

### Best sources for an 8086/8088 Python NASM implementation

| Source | Value for you | What it tests | Priority |
|---|---|---|---|
| **mininasm `test/`** | Excellent | Exhaustive 8086 encoding + real programs | **1** |
| **mininasm `xtest/`** | Excellent | NASM syntax, expressions, jumps, optimization | **2** |
| **NASM official `travis/`** | Very good after filtering | Regression/golden-output/error behavior | **3** |
| **Generated tests from NASM `insns.dat`** | Potentially best long-term | Systematic instruction/operand combinations | **4** |
| j-helland 8086 suite | Good | Real hand-written NASM programs | 5 |
| Yasm tests | Supplemental | Independent NASM-compatible implementation | 6 |

## 1. `pts/mininasm` has exactly the test suite you want

This is substantially more valuable for your project than trying to extract 8086 cases from modern NASM's enormous suite.

The author explicitly says the repository contains **a test for the full 8086/8088 instruction set**, and mininasm deliberately tries to produce binary output identical to NASM 0.98.39 at matching `-O0` / `-O999` optimization levels. :chatgpt-content-reference{index="0"}

[mininasm repository](https://github.com/pts/mininasm?utm_source=chatgpt.com)

The single most useful file I found is:

[test/input2.asm — exhaustive 8086 encoding corpus](https://github.com/pts/mininasm/blob/master/test/input2.asm?utm_source=chatgpt.com)

I inspected it directly. It is roughly **337 KB of assembly** and contains cases such as:

```asm
ADD [BX+SI],AL     ;00 00
ADD [BX+DI],AL     ;00 01
ADD [BP+SI],AL     ;00 02
...
ADD [BX+SI+0x55],AL
...
ADD [BX+SI+0x5566],AL
...
```

So it systematically walks through ModR/M combinations, registers, memory addressing, displacement forms and instruction encodings.

Even better, the repo contains the corresponding binary:

[test/INPUT2.IMG — golden binary output](https://github.com/pts/mininasm/blob/master/test/INPUT2.IMG?utm_source=chatgpt.com)

It is about 37 KB. Therefore your highest-value first test can simply be:

```text
input2.asm
     │
     ├── NASM/mininasm ──> INPUT2.IMG
     │
     └── pynasm ─────> ours.bin

assert ours.bin == INPUT2.IMG
```

No disassembler or semantic comparison is required.

There are also smaller foundation cases:

[input0.asm](https://github.com/pts/mininasm/blob/master/test/input0.asm?utm_source=chatgpt.com)  
[input1.asm — 8086 addressing modes](https://github.com/pts/mininasm/blob/master/test/input1.asm?utm_source=chatgpt.com)

`input1.asm`, for example, exercises:

```asm
mov cx,[bx]
mov cx,[bp]
mov cx,[si]
mov cx,[di]

mov cx,[bx+si]
mov cx,[bx+di]
mov cx,[bp+si]
mov cx,[bp+di]

mov cx,[bx+5]
mov cx,[bp+5]
...
mov cx,[bx+128]
...
```

That's particularly valuable because **8086 effective-address encoding is one of the easiest places to make subtle mistakes**.

---

## 2. mininasm `xtest/` is the next thing I would import wholesale

The second directory is:

[mininasm xtest/](https://github.com/pts/mininasm/tree/master/xtest?utm_source=chatgpt.com)

I inspected its contents. Particularly useful for your Python implementation are:

| Test | Purpose |
|---|---|
| `reg.nasm` | huge matrix of register/register instruction forms |
| `syntax.nasm` | NASM parsing and syntax |
| `arbyte.nasm` | arithmetic/immediate-size behavior |
| `cmpax.nasm` | special accumulator encodings |
| `cjump.nasm` | conditional branches |
| `jmpdist.nasm` | branch-distance boundaries |
| `jmpopt.nasm` | jump optimization |
| `iopt.nasm` | immediate optimization |
| `org.nasm` | `ORG` semantics |
| `lateorg.nasm` | unusual `ORG` placement |
| `ifdef.nasm` | preprocessor conditions |
| `xchg.nasm` | XCHG encoding selection |
| `simple.nasm` | general integration |
| `syntax.nasm` | parser + directives + expressions |

Two deserve special attention.

[xtest/reg.nasm](https://github.com/pts/mininasm/blob/master/xtest/reg.nasm?utm_source=chatgpt.com)

It contains large combinatorial matrices such as all:

```text
xchg r8,r8
xchg r16,r16
mov r8,r8
mov r16,r16
test r8,r8
test r16,r16
...
```

That's excellent encoder coverage.

Then:

[xtest/syntax.nasm](https://github.com/pts/mininasm/blob/master/xtest/syntax.nasm?utm_source=chatgpt.com)

starts explicitly with:

```asm
bits 16
cpu 8086
org 0x100
```

and tests labels, local labels, numeric syntax, expressions, `%include`, `byte`/`word`, `strict`, `jmp`, `call`, memory operands, far pointers, etc.

Importantly, its comments document the author's differential comparisons against multiple NASM versions, including NASM 0.98.39 and newer NASM releases. That maps directly onto what we need.

### Also take the negative convergence test

This one is unusually valuable:

[test/unstable.nasm](https://github.com/pts/mininasm/blob/master/test/unstable.nasm?utm_source=chatgpt.com)

It deliberately constructs an 8086 program whose jump relaxation cannot converge. The file documents how NASM 0.98.39, NASM 2.13 and mininasm respond.

That gives us a test for something that an instruction-by-instruction suite won't catch:

```text
lexer
 ↓
parser
 ↓
symbols
 ↓
layout
 ↓
branch relaxation
 ↓
layout changes
 ↓
repeat until stable
```

Your Python implementation must detect non-convergence rather than loop forever or silently generate inconsistent code.

---

## 3. The official NASM regression suite is useful, but needs filtering

Current NASM has both:

[NASM test/ directory](https://github.com/netwide-assembler/nasm/tree/master/test?utm_source=chatgpt.com)

and:

[NASM travis/ golden regression suite](https://github.com/netwide-assembler/nasm/tree/master/travis?utm_source=chatgpt.com)

The build explicitly has `test`/`travis` targets, and the repository contains both directories. :chatgpt-content-reference{index="12"}

The newer `travis/` system is more interesting for us. Each case generally has something like:

```text
xchg/
    xchg.asm
    xchg.json
    xchg.bin.t
```

where `.bin.t` is the golden result.

For example:

[NASM travis/xchg](https://github.com/netwide-assembler/nasm/tree/master/travis/xchg?utm_source=chatgpt.com)

and:

[NASM travis/ret](https://github.com/netwide-assembler/nasm/tree/master/travis/ret?utm_source=chatgpt.com)

`ret` contains separate reference results including `ret-16.bin.t`.

The official runner:

[tools/travis/nasm-t.py](https://github.com/netwide-assembler/nasm/blob/master/tools/travis/nasm-t.py?utm_source=chatgpt.com)

does exactly the kind of testing we want: execute NASM, compare binary output with golden data, compare stdout/stderr, and support tests expected to fail.

### But don't equate `BITS 16` with 8086

I searched NASM's current test tree for `bits 16` and found cases including:

```text
ret.asm
xchg.asm
test67.asm
jmpfar.asm
bintest.asm
immwarn.asm
lar_lsl.asm
inctest.asm
andbyte.asm
pushseg.asm
loopoffs.asm
obsolete.asm
prefix66.asm
smartalign16.asm
multisection.asm
...
```

Some of these deliberately exercise instructions or prefixes added **after 8086**.

So this filter is insufficient:

```python
if "bits 16" in source:
    run_test()
```

Instead the importer needs something like:

```python
if bits == 16 and all_instructions_are_8086(source):
    run_test()
```

or explicitly force:

```asm
cpu 8086
bits 16
```

and classify NASM rejection as expected when the source uses later instructions.

---

## 4. Generate a much larger suite automatically from NASM's ISA database

This could ultimately give your Python assembler stronger coverage than either existing suite.

NASM's canonical instruction descriptions live under:

[NASM x86/insns.dat](https://github.com/netwide-assembler/nasm/blob/master/x86/insns.dat?utm_source=chatgpt.com)

The entries carry CPU-generation information, so the test generator can select the **8086** forms.

I'd build a generator around that:

```text
NASM insns.dat
      │
      ├─ filter CPU <= 8086
      │
      ├─ enumerate registers
      ├─ enumerate immediates
      ├─ enumerate 8086 effective addresses
      ├─ displacement boundaries
      └─ branch boundaries
              ↓
        generated.asm
              ↓
       ┌──────────────┐
       │ NASM oracle  │
       └──────┬───────┘
              ↓
         golden.bin

generated.asm
      ↓
 pynasm
      ↓
  actual.bin
```

This is where I would aim for **tens or hundreds of thousands of individual encoding cases**, because generation is cheap.

Especially test boundaries rather than only arbitrary values:

```text
imm8:
    -129 -128 -127 -1 0 1 127 128 129
    0xff 0x100

disp8:
    -129 -128 -127 -1 0 1 127 128 129

imm16:
    -32769 -32768 -32767
    0x7fff 0x8000 0xffff 0x10000

relative:
    target = IP - 129
    target = IP - 128
    target = IP + 127
    target = IP + 128
```

These expose encoder bugs far more efficiently than random inputs.

---

## 5. An independent practical NASM corpus

`j-helland/8086-disassembler` has a directory of hand-written **8086 NASM sources** and uses NASM to assemble them as part of its tests. The project documents running its entire assembly corpus with `python test.py -d asm`. :chatgpt-content-reference{index="17"}

[8086-disassembler asm test corpus](https://github.com/j-helland/8086-disassembler/tree/master/asm?utm_source=chatgpt.com)

Examples include arithmetic, memory MOVs, SUBs and segment/offset notation.

This is not as exhaustive as mininasm, but it has a nice property: **it was written independently**. It can therefore expose places where both our implementation and a mininasm-derived test suite accidentally share the same assumption.

Yasm is another possible independent oracle because it is a separate rewrite of NASM that accepts NASM syntax. :chatgpt-content-reference{index="19"} I would use it only as a third opinion, though, not as the golden byte oracle: two assemblers may legitimately select different equivalent encodings.

---

# The test stack I would use for our Python port

I would make **NASM 0.98.39 compatibility a precisely defined compatibility profile**, rather than vaguely saying "NASM compatible." This matters because mininasm explicitly notes that newer NASM versions have changed encoding/optimization behavior over time; mininasm intentionally targets byte-identical NASM 0.98.39 behavior. :chatgpt-content-reference{index="20"}

I'd therefore structure the project around:

```text
tests/
    mininasm/
        input0.asm
        input1.asm
        input2.asm
        ...
    syntax/
        syntax.nasm
        reg.nasm
        ...
    nasm_official/
        ...
    generated/
        arithmetic.asm
        modrm.asm
        branches.asm
        strings.asm
        prefixes.asm
        ...
    negative/
        cpu_186.asm
        cpu_286.asm
        invalid_address.asm
        invalid_reg_size.asm
        unstable_labels.asm
    programs/
        bootbasic.asm
        rogue.asm
        invaders.asm
        ...
```

And require four separate properties:

```text
1. VALID 8086 INPUT
   Python accepts it.

2. EXACT ENCODING
   Python output == pinned golden bytes.

3. INVALID INPUT
   Python rejects it.

4. NON-8086 INPUT
   Python rejects 186/286/386+ instructions.
```

For **8088**, you don't need a second assembler corpus: the 8086 and 8088 have the same instruction encoding/ISA. Separate 8088 testing becomes relevant when executing the code—timings, prefetch queue and bus behavior—not when assembling it.

The single best first milestone is therefore: **make our Python assembler pass `mininasm/test/input2.asm` byte-for-byte against `INPUT2.IMG`, then run `xtest/reg.nasm` and `xtest/syntax.nasm`.** After that, add generated tests from NASM's `insns.dat`. That gives a much stronger definition of "8086 NASM compatible" than merely compiling a handful of DOS programs.
