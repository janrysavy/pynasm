"""Small NASM-compatible command line for flat binary assembly."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .assembler import Assembler, AssemblyError
from .listing import render_listing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pynasm", description="Pure Python 8086/8088 assembler")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("-l", "--listing", type=Path, help="write an expanded-source byte listing")
    parser.add_argument("-f", "--format", default="bin", choices=["bin"])
    parser.add_argument("-I", "-i", "--include", action="append", default=[], metavar="DIR")
    parser.add_argument("-p", "--pre-include", action="append", default=[], metavar="FILE")
    parser.add_argument("-D", "--define", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("-O", "--optimize", nargs="?", const="1", default="0", metavar="LEVEL")
    parser.add_argument("--compatibility", choices=["nasm09839", "nasm3"], default="nasm09839")
    args = parser.parse_args(argv)
    definitions = {}
    for item in args.define:
        name, _, value = item.partition("=")
        definitions[name] = value
    target = args.output or args.source.with_suffix(".bin")
    outputs = [target] + ([args.listing] if args.listing is not None else [])
    def aliases(a: Path, b: Path) -> bool:
        return a.resolve() == b.resolve() or (a.exists() and b.exists() and a.samefile(b))
    try:
        if any(aliases(path, args.source) for path in outputs):
            raise ValueError("output must not overwrite the source file")
        if len(outputs) == 2 and aliases(*outputs):
            raise ValueError("binary and listing outputs must be different files")
        for path in outputs:
            path.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        print(f"pynasm: {exc}", file=sys.stderr)
        return 1
    try:
        level = 9 if args.optimize.lower() == "x" else int(args.optimize)
        assembler = Assembler(optimize=level, include_paths=args.include, preincludes=args.pre_include,
                              defines=definitions,
                              compatibility=args.compatibility)
        binary = assembler.assemble(args.source.read_text(encoding="latin-1"), filename=str(args.source.resolve()))
        target.write_bytes(binary)
        if args.listing is not None:
            args.listing.write_text(render_listing(assembler.listing), encoding="utf-8", newline="\n")
    except (AssemblyError, OSError, ValueError) as exc:
        for path in outputs:
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup:
                print(f"pynasm: cannot remove failed output {path}: {cleanup}", file=sys.stderr)
        print(f"pynasm: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
