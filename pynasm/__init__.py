"""Pure Python 8086/8088 flat binary assembler."""

from .assembler import Assembler, AssemblyError, assemble

__all__ = ["Assembler", "AssemblyError", "assemble"]
