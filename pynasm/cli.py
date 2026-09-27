"""Small NASM-compatible command line for flat binary assembly."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .assembler import Assembler, AssemblyError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pynasm", description="Pure Python 8086/8088 assembler")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("-f", "--format", default="bin", choices=["bin"])
    parser.add_argument("-I", "--include", action="append", default=[], metavar="DIR")
    parser.add_argument("-p", "--pre-include", action="append", default=[], metavar="FILE")
    parser.add_argument("-D", "--define", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("-O", "--optimize", nargs="?", const="1", default="0", metavar="LEVEL")
    parser.add_argument("--compatibility", choices=["nasm09839", "nasm3"], default="nasm09839")
    args = parser.parse_args(argv)
    definitions = {}
    for item in args.define:
        name, _, value = item.partition("=")
        definitions[name] = value
    try:
        level = 9 if args.optimize.lower() == "x" else int(args.optimize)
        assembler = Assembler(optimize=level, include_paths=args.include, preincludes=args.pre_include,
                              defines=definitions,
                              compatibility=args.compatibility)
        binary = assembler.assemble(args.source.read_text(encoding="latin-1"), filename=str(args.source.resolve()))
        target = args.output or args.source.with_suffix(".bin")
        target.write_bytes(binary)
    except (AssemblyError, OSError, ValueError) as exc:
        print(f"pynasm: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
