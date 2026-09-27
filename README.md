# pynasm

**pynasm** is a pure-Python assembler for the 8086 and 8088. It reads NASM-style
source and writes flat binaries, with no native runtime dependency.

## Quick start

From this repository, save the following as `exit.asm`:

```nasm
cpu 8088
bits 16
org 0x100
mov ax, 0x4c00
int 0x21
```

Assemble it with:

```console
python -m pynasm --compatibility nasm3 -o exit.com exit.asm
```

You can also use the Python API:

```python
from pynasm import assemble

binary = assemble("cpu 8088\nmov ax, 0x1234")
assert binary == bytes.fromhex("b8 34 12")
```

Install with `python -m pip install .` if you want the `pynasm` command on your
PATH. Run `pynasm --help` for the available options.

## Compatibility

The 8086 and 8088 use the same instruction encodings. `cpu 8088` is a pynasm
alias; NASM itself calls this target `cpu 8086`.

pynasm supports 8086 integer instructions, the 8087 forms NASM permits for
this CPU, 16-bit addressing, labels and branch sizing, data directives,
expressions, includes, and a substantial part of NASM's macro language.
The CLI accepts include paths (`-I` or `-i`, separate or attached), preinclude files (`-p`), definitions
(`-D`), and optimization levels (`-O`).

The default compatibility profile follows NASM 0.98.39 encoding choices. Use
`--compatibility nasm3` for behavior checked against NASM 3.02. Output is
currently limited to flat binaries (`-f bin`); full NASM compatibility is
still in progress.

The CLI removes an existing output before assembly and removes partial output
on failure, so a failed build cannot leave a stale binary looking successful.
The main source cannot also be the output (including hard-link aliases). Keep
output paths separate from include files and other build inputs as well.

## Expanded byte listings

`python -m pynasm --compatibility nasm3 -Ox -l program.lst -o program.bin program.asm`
writes an expanded-source listing from the final converged assembly pass. Rows
show logical source line numbers, section-relative offsets and resolved bytes;
comments identify source files and sections. Long byte rows wrap at eight bytes.
BSS and ABSOLUTE reservations show their sizes without claiming file bytes.
Implicit section-alignment padding has no source row.

The API exposes the same data as immutable `Assembler.listing` records after
successful assembly, including separate `address` (virtual), `offset` (within
section), `file_offset` (physical, or `None`), `size`, `data`, `filename`, `number`
and expanded `text`. A new assembly clears the previous listing, including on
failure. Binary and listing outputs must be distinct; CLI failure removes both.

This is an expanded listing, not a byte-for-byte implementation of NASM's
listing format: it does not reproduce macro invocation/include nesting events,
suppressed preprocessor lines, or symbolic relocation brackets. Consumers of
NASM's event/depth columns must not substitute it without adapting their parser.
OMF object output remains unsupported.

## Tests and progress

Run the bundled tests with:

```console
python -m unittest discover -s tests
```

The suite includes pinned NASM and mininasm binaries. Live differential tests
need a separate NASM installation. See the [test plan](doc/TESTS.md) for those
commands and the [progress tracker](doc/PROGRESS.md) for the current status.
CI runs Python 3.12 on Windows and Linux against the pinned corpora, setting
`NASM` to an empty string to disable discovery of unpinned runner executables.
For live differential tests, set `NASM` to a NASM 3.02 executable path.
The [future test roadmap](doc/FUTURE_TESTS.md) lists the remaining work in
priority order.
The original design discussion is in [PLAN.md](doc/PLAN.md).

## License

The project code is [BSD-2-Clause](LICENSE). Bundled mininasm and NASM test
fixtures retain their upstream notices and licenses in
[MININASM_LICENSE](doc/MININASM_LICENSE) and [NASM_LICENSE](doc/NASM_LICENSE).
