This is the original design discussion. The active plan for remaining tests is
in [FUTURE_TESTS.md](FUTURE_TESTS.md); completed checks are in
[TESTS.md](TESTS.md).

NASM is technically an **assembler**, and after looking at the available open-source implementations I would **not port NASM itself** for an 8086/8088-only Python assembler. There is a substantially better starting point.

### Best candidates

| Approach | Size / complexity | NASM compatibility | 8086/8088 fit | Recommendation |
|---|---:|---:|---:|---|
| **Port `mininasm` C → Python** | Small/medium | High for useful 16-bit subset | Excellent | **Best** |
| Port reduced NASM | Large | Highest | Excellent after stripping | Only if modern NASM compatibility is essential |
| Port Tinyasm | Small | Moderate | Excellent | Good prototype, weaker foundation |
| New table-driven Python assembler | Small | Whatever you implement | Excellent | Attractive if syntax needs are narrow |
| Keystone Python bindings | Huge native dependency | Different goal | Supports x86-16 | Not a pure-Python solution |

## 1. Best solution: port **mininasm**

This project almost exactly matches what you're asking for:

[pts/mininasm on GitHub](https://github.com/pts/mininasm?utm_source=chatgpt.com)

It is explicitly a **minimal NASM-compatible assembler for 8086/8088, 186 and 286**, written in C. The current `mininasm.c` is only about **4,080 lines / 3,919 LOC**, and quite a lot of that code exists only to support ancient DOS C compilers, custom allocation, 16-bit memory models and libc portability—things that disappear in Python. :chatgpt-content-reference{index="1"}

More importantly, it already solved the annoying assembler problems:

- all 8086 instructions, apart from floating point;
- ModR/M and 16-bit effective-address encoding;
- labels and forward references;
- local labels;
- short/near branches and multipass optimization;
- `byte` / `word` / `strict`;
- `org`, `times`, `db`, `dw`, `dd`, `align`;
- `%define`, `%if`, `%ifdef`, `%include`, etc.;
- expressions;
- raw binary output;
- NASM-like command line;
- compatibility tests.

It specifically tries to generate **byte-identical output to NASM 0.98.39** for supported input, including NASM's encoding choices at corresponding optimization levels. :chatgpt-content-reference{index="2"}

The license is **BSD-2-Clause**, so a Python port is straightforward from a licensing perspective. :chatgpt-content-reference{index="3"}

One important simplification: **8086 and 8088 have the same instruction set**. The 8088 differs primarily in its external 8-bit bus/prefetch/timing characteristics. You need only one encoder target, effectively `CPU_8086`.

### How I would port it

I would make it a semantic port, **not a line-by-line C translation**:

```text
pynasm/
    lexer.py
    expression.py
    operand.py
    isa8086.py
    encoder.py
    symbols.py
    preprocessor.py
    assembler.py
    listing.py
```

`isa8086.py` should be declarative. For example, conceptually:

```python
Instruction(
    "mov",
    operands=(REG16, IMM16),
    encoding=OpcodePlusReg(0xB8, imm16=True)
)

Instruction(
    "mov",
    operands=(RM16, REG16),
    encoding=ModRM(opcode=0x89, reg_operand=1, rm_operand=0)
)
```

Do **not** reproduce mininasm's extreme C compactness. Python makes a typed internal representation much easier to test.

I would initially completely remove:

```text
80186
80286
32/64-bit operands
protected mode
FPU
object formats
DOS-host compatibility
ancient-C portability
custom allocators
```

That leaves surprisingly little assembler logic.

---

## 2. Use NASM itself as the specification and test oracle

The official source is here:

[Official NASM repository](https://github.com/netwide-assembler/nasm?utm_source=chatgpt.com)

NASM is also BSD-2-Clause. :chatgpt-content-reference{index="5"}

However, NASM itself is now much larger than the problem you want to solve. The assembler includes separate parser, evaluator, preprocessor, labels, listing, output modules and many generated tables. Its build system generates several instruction-related C files from the x86 database. :chatgpt-content-reference{index="6"}

The instruction database alone is currently about **6,005 lines / 474 KB**, covering everything from 8086 through contemporary x86 extensions. :chatgpt-content-reference{index="7"}

So I would use NASM for:

```text
specification
differential testing
error-behavior reference
encoding-choice reference
```

rather than as the codebase to translate.

A very strong test harness would do:

```python
source -> your Python assembler -> ours.bin
source -> NASM              -> nasm.bin

assert ours.bin == nasm.bin
```

for tens or hundreds of thousands of generated legal operand combinations.

Also run deliberately invalid combinations and ensure your assembler rejects them.

---

## 3. Interesting alternative: derive the Python encoder from NASM `insns.dat`

There is a more ambitious approach that I like architecturally.

NASM keeps its ISA descriptions in:

[NASM x86/insns.dat](https://github.com/netwide-assembler/nasm/blob/master/x86/insns.dat?utm_source=chatgpt.com)

Entries look conceptually like:

```text
INT     imm8       [...]     8086
CLC     void       [...]     8086
CALL    rm16       [...]     8086
```

and explicitly carry CPU-generation flags such as `8086`, `186`, etc. :chatgpt-content-reference{index="9"}

You could therefore write:

```text
insns.dat
    ↓
Python generator
    ↓ filter CPU == 8086
isa8086_generated.py
```

This is appealing because the ISA description stays tied to NASM upstream.

But there is a catch.

The third field of `insns.dat` is essentially an **encoding DSL**, and NASM itself says its interpretation is defined by `insns.pl` and `assemble.c`. :chatgpt-content-reference{index="10"}

So parsing:

```text
8086
```

is easy.

Implementing the complete meaning of:

```text
[m: nw o# ff /2]
[i: cd ib,u]
...
```

is effectively porting part of NASM's encoder.

### A better hybrid

Use NASM's database as an **input/reference**, but convert the 8086 subset once into your own clean representation:

```python
Encoding(
    mnemonic="add",
    operands=(RM16, REG16),
    opcode=b"\x01",
    modrm=ModRM(reg=1, rm=0),
    cpu=CPU_8086,
)
```

Check the generated Python table into Git.

That gives you both traceability to NASM and a pleasant runtime architecture.

---

## 4. Tinyasm is worth studying, but I would port mininasm instead

`mininasm` itself was derived from Oscar Toledo's **Tinyasm**, which was created specifically as a NASM-like assembler capable of running on an actual 8086/8088 PC. Tinyasm deliberately uses a very simple pattern-matching design. :chatgpt-content-reference{index="11"}

That sounds ideal, but mininasm subsequently added:

- critical bug fixes;
- more deterministic behavior;
- closer NASM compatibility;
- richer expressions;
- more directives;
- better optimization behavior;
- much more testing.

The mininasm documentation explicitly describes these improvements over Tinyasm. :chatgpt-content-reference{index="12"}

So Tinyasm is useful to understand the minimum viable design, but **mininasm is the code I would actually port**.

---

## 5. I would not choose Keystone

Keystone supports x86 **16/32/64-bit** and has Python bindings, so at first glance it looks tempting. But the actual assembler is C/C++/LLVM-derived native code; Python is only a binding. It therefore doesn't achieve a Python-native assembler. Its licensing is also GPLv2/commercial rather than the permissive BSD license used by NASM/mininasm. :chatgpt-content-reference{index="13"}

So it solves a different problem.

There are also tiny Python 8086 assemblers such as `mjkarki/asm8086`, but its author explicitly describes it as a toy assembler, and its architecture is far below the NASM compatibility level you're looking for. :chatgpt-content-reference{index="14"}

## What I would build

My preferred architecture is therefore:

**mininasm semantics + clean Python rewrite + 8086-only ISA table + differential testing against NASM and mininasm.**

I would *not* even implement the preprocessor initially. The milestones I'd use are:

1. lexer + expressions;
2. `db`/`dw`, `org`, labels;
3. complete 8086 register/immediate instruction encoding;
4. complete 8086 effective-address/ModR/M encoding;
5. branches + forward references;
6. multipass branch relaxation;
7. segment overrides and prefixes;
8. NASM size qualifiers;
9. `times` / `incbin` / local labels;
10. only then `%define`, `%include`, `%if`, macros as required.

The critical design choice is to make instruction encoding **data-driven**, rather than creating something like:

```python
if mnemonic == "mov":
    ...
elif mnemonic == "add":
    ...
elif mnemonic == "sub":
    ...
```

A clean table-driven encoder will probably end up being only a few thousand lines of Python including the instruction descriptions, while still being substantially easier to verify than a partial translation of modern NASM.

For your use case, I'd target **byte-exact assembly rather than source-feature completeness**: if the Python implementation accepts a file, its output should be exactly what the chosen NASM reference version emits. That's much more valuable for DOS binary reconstruction than supporting every obscure NASM preprocessor feature.

**So my recommendation is very strongly: fork `pts/mininasm`, freeze its 8086 behavior, remove 186/286 support, and translate that design into clean Python. Use official NASM as the differential oracle, not as the porting source.**
