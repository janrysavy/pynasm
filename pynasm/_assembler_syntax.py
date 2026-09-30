"""Shared source models, tokens, and low-level assembly helpers."""

from __future__ import annotations

import ast
import os
import re
import time
import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path

from .expression import ExpressionError, Value, _number, evaluate, evaluate_address, string_bytes
from .floatdata import encode_bcd, encode_float, float_operator
from .fpu8087 import FPU_FIXED, FPU_MEMORY, FPU_MNEMONICS, FPU_REGISTER
from .isa8086 import ALU, FIXED, JCC, PREFIX, REG8, REG16, SEGREG, SEG_PREFIX, SHIFT, UNARY_GROUP

ADDRESS_PREFIX = {"a16": 16, "a32": 32}
OPERAND_PREFIX = {"o16": 16, "o32": 32}
KNOWN_MNEMONICS = (set(FIXED) | set(PREFIX) | set(ADDRESS_PREFIX) |
                   set(OPERAND_PREFIX) |
                   set(ALU) | set(JCC) | set(SHIFT) |
                   set(FPU_MNEMONICS) |
                   set(UNARY_GROUP) | {"mov", "movabs", "movsx", "movsxb", "bswap",
                   "test", "xchg", "lea", "lds", "les",
                   "in", "out", "jmp", "call", "push", "pop", "inc", "dec",
                   "ret", "retw", "retn", "retnw", "retf", "retfw",
                   "aad", "aam", "int", "db", "dw",
                   "dd", "dq", "dt", "do", "dy", "dz", "bf16",
                   "resb", "resw", "resd", "resq", "rest", "reso", "resy", "resz", "align",
                   "alignb", "alignmode", "incbin", "times", "org", "bits", "cpu",
                   "use16", "section", "segment", "absolute", "sectalign", "global",
                   "default", "dollarhex", "float", "list", "debug", "static",
                   "extern", "required", "prefix", "suffix", "postfix",
                   "gprefix", "gsuffix", "gpostfix", "lprefix", "lsuffix",
                   "lpostfix"})

MODERN_ONLY_MNEMONICS = {
    "brkpt", "int03", "fwait", "iretw", "pushfw", "popfw",
    "retw", "retnw", "retfw", "movabs", "movsx", "movsxb", "bswap",
    "loopw", "loopew", "loopnew", "loopzw", "loopnzw",
}

_PP_TOKEN = re.compile(r"`(?:[^`\\]|\\.)*`|'[^']*'|\"[^\"]*\"|"
                       r"[A-Za-z_.$?@][\w.$?@~#]*|[0-9][\w]*|"
                       r"<=>|<<<|>>>|<<|>>|//|%%|==|!=|<>|<=|>=|&&|\|\||\^\^|[^\s]")
_PP_CONDITIONS = {
    "%if", "%ifn", "%ifdef", "%ifndef", "%ifdefalias", "%ifndefalias",
    "%ifidn", "%ifnidn", "%ifidni", "%ifnidni",
    "%ifid", "%ifnid", "%ifnum", "%ifnnum", "%ifstr", "%ifnstr",
    "%iftoken", "%ifntoken", "%ifempty", "%ifnempty", "%ifmacro", "%ifnmacro",
    "%ifenv", "%ifnenv", "%ifctx", "%ifnctx", "%iffile", "%ifnfile",
    "%ifdirective", "%ifndirective", "%ifdifi", "%ifndifi",
    "%ifusable", "%ifnusable", "%ifusing", "%ifnusing",
}
_PP_INVERSE_CONDITIONS = {
    code: inverse
    for left, right in (
        ("a", "na"), ("ae", "nae"), ("b", "nb"), ("be", "nbe"),
        ("c", "nc"), ("e", "ne"), ("g", "ng"), ("ge", "nge"),
        ("l", "nl"), ("le", "nle"), ("o", "no"), ("p", "np"),
        ("pe", "po"), ("s", "ns"), ("z", "nz"),
    )
    for code, inverse in ((left, right), (right, left))
}
_PP_INVERSE_CONDITIONS.update({"cxz": None, "ecxz": None, "rcxz": None})
_NASM_USE_PACKAGES = {"altreg", "fp", "ifunc", "masm", "smartalign", "vtern"}
_SMARTALIGN_DEFAULT_THRESHOLD = {"nop": 16, "generic": 8, "k7": 16,
                                 "k8": 16, "p6": 16}
_SMARTALIGN_16 = {
    "nop": ("", "90"),
    "generic": ("", "90", "89f6", "8d7400", "8db40000",
                "8db4000090", "8db4000089ff", "8db400008d7d00",
                "8db400008dbd0000"),
    "k7": ("", "90", "6690", "666690", "66666690"),
    "k8": ("", "90", "6690", "666690", "66666690"),
    "p6": ("", "90", "6690", "0f1f00", "0f1f4000"),
}
_SMARTALIGN_16 = {name: tuple(bytes.fromhex(code) for code in patterns)
                  for name, patterns in _SMARTALIGN_16.items()}

_NASM_DIRECTIVES = {
    "absolute", "bits", "common", "cpu", "debug", "default", "dollarhex",
    "extern", "float", "global", "list", "pragma", "required", "sectalign",
    "section", "segment", "static", "warning", "prefix", "suffix", "postfix",
    "gprefix", "gsuffix", "gpostfix", "lprefix", "lsuffix", "lpostfix",
    "db", "dw", "dd", "dq", "dt", "do", "dy", "dz", "resb", "resw",
    "resd", "resq", "rest", "reso", "resy", "resz", "incbin", "equ",
    "map", "org",
}
_PP_DIRECTIVE_SUFFIXES = {
    "", "ctx", "def", "defalias", "difi", "directive", "empty", "env",
    "file", "id", "idn", "idni", "macro", "num", "str", "token",
    "usable", "using",
}
_NASM_PP_DIRECTIVES = {
    "%" + name for name in (
        "assign", "iassign", "defalias", "idefalias", "define", "idefine",
        "defstr", "idefstr", "deftok", "ideftok", "macro", "imacro",
        "pathsearch", "ipathsearch", "rmacro", "irmacro", "strcat", "istrcat",
        "strlen", "istrlen", "substr", "isubstr", "xdefine", "ixdefine",
        "unmacro", "unimacro", "aliases", "arg", "clear", "depend",
        "else", "endif", "endm", "endmacro", "endrep", "error",
        "exitmacro", "exitrep", "fatal", "include", "line", "local",
        "null", "note", "pop", "pragma", "push", "rep", "repl",
        "require", "rotate", "stacksize", "undef", "undefalias",
        "use", "warning",
    )
} | {
    "%" + stem + negation + suffix
    for stem in ("if", "elif")
    for negation in ("", "n")
    for suffix in _PP_DIRECTIVE_SUFFIXES
}


def _pp_tokens(source: str) -> list[str]:
    return _PP_TOKEN.findall(source)


def _expand_smacro_self_reference(body: str, invoked: str, declared: str) -> str:
    pieces = re.split(r"('[^']*'|\"[^\"]*\"|`(?:[^`\\]|\\.)*`)", body)
    for index in range(0, len(pieces), 2):
        pieces[index] = re.sub(
            r"%\*\?\?|%\*\?|%\?\?|%\?",
            lambda match: declared if match.group().endswith("??") else invoked,
            pieces[index])
    return "".join(pieces)


_SMACRO_BODY_TOKEN = re.compile(
    r"`(?:[^`\\]|\\.)*`|'[^']*'|\"[^\"]*\"|%,|\s+|"
    r"[A-Za-z_.$?@][\w.$?@~#]*|.")


def _substitute_smacro_arguments(body: str, replacements: dict[str, str],
                                 expanded: dict[str, str],
                                 insensitive: bool) -> str:
    output: list[str] = []
    following_nonempty = False
    for token in reversed(_SMACRO_BODY_TOKEN.findall(body)):
        key = token.lower() if insensitive else token
        if token == "%,":
            output.append("," if following_nonempty else "")
        elif key in replacements:
            output.append(replacements[key])
            following_nonempty = bool(expanded[key].strip())
        else:
            output.append(token)
            if token.strip():
                following_nonempty = True
    return "".join(reversed(output))


class AssemblyError(ValueError):
    def __init__(self, message: str, filename: str = "<string>", line: int = 0):
        super().__init__(f"{filename}:{line}: {message}" if line else message)


@dataclass(frozen=True)
class SourceLine:
    text: str
    filename: str
    number: int


@dataclass
class MacroInvocation:
    arguments: list[str]
    prefix: str
    conditional_depth: int
    repetition_depth: int
    invocation_label: str | None = None
    reported_count: int | None = None
    invoked_name: str | None = None
    declared_name: str | None = None


@dataclass
class MacroDefinition:
    minimum: int
    maximum: int
    body: list[str]
    case_insensitive: bool
    defaults: list[str]
    greedy: bool
    locations: list[SourceLine] | None = None
    name: str | None = None
    order: int = 0


@dataclass(frozen=True)
class SmacroParameter:
    name: str
    greedy: bool = False
    evaluate: bool = False
    quote: int = 0
    no_strip: bool = False
    radix: str = ""
    unsigned: bool = False


@dataclass
class SmacroDefinition:
    parameters: list[SmacroParameter]
    body: str
    name: str = ""
    case_insensitive: bool = False
    order: int = 0


@dataclass
class Operand:
    kind: str
    width: int | None = None
    reg: int = 0
    expr: Value = field(default_factory=lambda: Value(0))
    segment: str | None = None
    base: tuple[str, ...] = ()
    qualifier: str | None = None
    strict: bool = False
    far_segment: Value | None = None
    distance_flags: frozenset[str] = frozenset()
    displacement_width: int | None = None
    direct_byte_form: bool = False
    address_width: int | None = None
    # NASM3 selects relative based-address displacements before flat relocation.
    selection_displacement: int | None = None


@dataclass
class Section:
    name: str
    align: int = 4
    nobits: bool = False
    start: int | None = None
    vstart: int | None = None
    size: int = 0
    file_start: int = 0
    base: int = 0
    data: bytearray = field(default_factory=bytearray)
    follows: str | None = None
    vfollows: str | None = None


def _split(text: str, sep: str = ",", *, macro: bool = False) -> list[str]:
    result, quote, depth, start, escaped = [], None, 0, 0, False
    for i, char in enumerate(text):
        if quote:
            if char == quote and not escaped: quote = None
            if quote == "`" and char == "\\" and not escaped: escaped = True
            else: escaped = False
        elif char in "'\"`": quote = char
        elif char in ("{" if macro else "[({"): depth += 1
        elif char in ("}" if macro else "])}"): depth -= 1
        elif char == sep and depth == 0:
            result.append(text[start:i].strip())
            start = i + 1
    result.append(text[start:].strip())
    return result


def _split_smacro_arguments(text: str, *, strip: bool = True) -> list[str]:
    result: list[str] = []
    quote = None
    escaped = False
    braces = 0
    parentheses = 0
    start = 0
    for index, char in enumerate(text):
        if quote:
            if char == quote and not escaped:
                quote = None
            if quote == "`" and char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False
        elif char in "'\"`":
            quote = char
        elif char == "{":
            braces += 1
        elif char == "}" and braces:
            braces -= 1
        elif char == "(" and not braces:
            parentheses += 1
        elif char == ")" and not braces and parentheses:
            parentheses -= 1
        elif char == "," and not braces and not parentheses:
            item = text[start:index]
            result.append(item.strip() if strip else item)
            start = index + 1
    item = text[start:]
    result.append(item.strip() if strip else item)
    return result


def _collapse_unquoted_whitespace(source: str) -> str:
    pieces = re.split(r"('[^']*'|\"[^\"]*\"|`(?:[^`\\]|\\.)*`)", source)
    for index in range(0, len(pieces), 2):
        pieces[index] = re.sub(r"\s+", " ", pieces[index])
    return "".join(pieces)


def _unbrace_macro_argument(argument: str) -> str:
    if not argument.startswith("{") or not argument.endswith("}"):
        return argument
    depth = 0
    quote = None
    escaped = False
    for index, char in enumerate(argument):
        if quote:
            if char == quote and not escaped:
                quote = None
            if quote == "`" and char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and index != len(argument) - 1:
                return argument
    return argument[1:-1] if depth == 0 else argument


def _comment(text: str) -> str:
    quote, escaped = None, False
    for i, char in enumerate(text):
        if quote:
            if char == quote and not escaped: quote = None
            if quote == "`" and char == "\\" and not escaped: escaped = True
            else: escaped = False
        elif char in "'\"`": quote = char
        elif char == ";": return text[:i]
    return text


def _unbrace_pp_tokens(text: str) -> str:
    if "%{" not in text:
        return text
    output: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == ";":
            output.append(text[index:])
            break
        if text[index] in "'\"`":
            quote = text[index]
            end = index + 1
            while end < len(text):
                if text[end] == quote and (quote != "`" or text[end - 1] != "\\"):
                    end += 1
                    break
                end += 1
            output.append(text[index:end])
            index = end
            continue
        if not text.startswith("%{", index):
            output.append(text[index])
            index += 1
            continue
        depth = 1
        end = index + 2
        while end < len(text) and depth:
            if text[end] in "'\"`":
                quote = text[end]
                end += 1
                while end < len(text):
                    if text[end] == quote and (quote != "`" or text[end - 1] != "\\"):
                        end += 1
                        break
                    end += 1
                continue
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
            end += 1
        if depth:
            output.append(text[index:])
            break
        content = text[index + 2:end - 1]
        if re.fullmatch(r"[0-9]+|-?[0-9]+:-?[0-9]+", content):
            output.append(text[index:end])
        else:
            output.append("%" + content)
        index = end
    return "".join(output)


def _quote_string(value: str) -> str:
    if "'" not in value:
        return "'" + value + "'"
    if '"' not in value:
        return '"' + value + '"'
    return "`" + value.replace("\\", "\\\\").replace("`", "\\`") + "`"


def _expand_environment(text: str) -> tuple[str, bool]:
    pieces: list[str] = []
    index = 0
    changed = False
    while index < len(text):
        if text.startswith("%!", index):
            start = index + 2
            if start < len(text) and text[start] in "'\"`":
                quote = text[start]
                end = text.find(quote, start + 1)
                if end >= 0:
                    pieces.append(os.environ.get(text[start + 1:end], ""))
                    index = end + 1
                    changed = True
                    continue
            match = re.match(r"[A-Za-z_][\w]*", text[start:])
            if match:
                pieces.append(os.environ.get(match.group(), ""))
                index = start + len(match.group())
                changed = True
                continue
        if text[index] in "'\"`":
            quote = text[index]
            end = index + 1
            while end < len(text):
                if text[end] == quote and (quote != "`" or text[end - 1] != "\\"):
                    end += 1
                    break
                end += 1
            pieces.append(text[index:end])
            index = end
            continue
        pieces.append(text[index])
        index += 1
    return "".join(pieces), changed


def _word(value: int, width: int) -> bytes:
    return (value & ((1 << (width * 8)) - 1)).to_bytes(width, "little")


def _signed8(value: int) -> bool:
    return -128 <= value <= 127 or 0xFF80 <= value <= 0xFFFF


def _signed8_word(value: int) -> bool:
    narrowed = value & 0xFFFF
    return narrowed <= 0x7F or narrowed >= 0xFF80


def _modrm(reg: int, rm: Operand, width: int, conservative: bool = False) -> bytes:
    if rm.kind == "reg":
        if rm.width != width: raise AssemblyError("operand sizes do not match")
        return bytes((0xC0 | (reg << 3) | rm.reg,))
    if rm.kind != "mem": raise AssemblyError("register or memory operand expected")
    if rm.width and rm.width != width: raise AssemblyError("operand sizes do not match")
    bases = frozenset(rm.base)
    if len(bases) != len(rm.base): raise AssemblyError("invalid 8086 effective address")
    codes = {
        frozenset(("bx", "si")): 0, frozenset(("bx", "di")): 1,
        frozenset(("bp", "si")): 2, frozenset(("bp", "di")): 3,
        frozenset(("si",)): 4, frozenset(("di",)): 5,
        frozenset(("bp",)): 6, frozenset(("bx",)): 7,
    }
    if bases and bases not in codes: raise AssemblyError("invalid 8086 effective address")
    disp = rm.expr.number & 0xFFFF
    if not bases:
        if rm.address_width == 32 or rm.displacement_width == 32:
            return bytes((0x05 | (reg << 3),)) + _word(rm.expr.number, 4)
        return bytes((0x06 | (reg << 3),)) + _word(disp, 2)
    code = codes[bases]
    selection = disp if rm.selection_displacement is None else rm.selection_displacement & 0xFFFF
    known_scalar = not rm.expr.relocation or rm.selection_displacement is not None
    if rm.displacement_width == 8:
        mod, extra = 1, _word(selection, 1)
    elif rm.displacement_width == 16:
        mod, extra = 2, _word(disp, 2)
    elif (not conservative and not rm.expr.unresolved and known_scalar and
          selection == 0 and bases != frozenset(("bp",))):
        mod, extra = 0, b""
    elif (not conservative and not rm.expr.unresolved and known_scalar and
          _signed8_word(selection)):
        mod, extra = 1, _word(selection, 1)
    else:
        mod, extra = 2, _word(disp, 2)
    return bytes(((mod << 6) | (reg << 3) | code,)) + extra

# Export the implementation's shared names to the focused internal modules.
__all__ = [name for name in globals() if not name.startswith('__')]
