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
The CLI accepts include paths (`-I`), preinclude files (`-p`), definitions
(`-D`), and optimization levels (`-O`).

The default compatibility profile follows NASM 0.98.39 encoding choices. Use
`--compatibility nasm3` for behavior checked against NASM 3.02. Output is
currently limited to flat binaries (`-f bin`); full NASM compatibility is
still in progress.

## Tests and progress

Run the bundled tests with:

```console
python -m unittest discover -s tests
```

The suite includes pinned NASM and mininasm binaries. Live differential tests
need a separate NASM installation. See the [test plan](doc/TESTS.md) for those
commands and the [progress tracker](doc/PROGRESS.md) for the current status.
The [future test roadmap](doc/FUTURE_TESTS.md) lists the remaining work in
priority order.
The original design discussion is in [PLAN.md](doc/PLAN.md).

## License

The project code is [BSD-2-Clause](LICENSE). Bundled mininasm and NASM test
fixtures retain their upstream notices and licenses in
[MININASM_LICENSE](doc/MININASM_LICENSE) and [NASM_LICENSE](doc/NASM_LICENSE).
