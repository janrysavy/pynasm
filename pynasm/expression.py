"""NASM-style integer expressions. Values are Python integers until emitted."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Callable

from ._string_escapes import unquote_backtick
from ._layout import Layout, combine_layout, scale_layout


class ExpressionError(ValueError):
    pass


_TOKEN = re.compile(
    r"\s*(<=>|<<<|>>>|<<|>>|//|%%|==|!=|<>|<=|>=|&&|\|\||\^\^|\$\$|"
    r"\$[0-9a-fA-F_]+(?![\w.$?@~#])|\$[A-Za-z_.$?@][\w.$?@~#]*|\?(?![\w.$?@~#])|[()+\-*/%&|^~<>:$!=]|[A-Za-z_.$?@][\w.$?@~#]*|"
    r"[0-9][0-9a-zA-Z_]*|"
    r"'[^']*'|\"[^\"]*\"|`(?:[^`\\]|\\.)*`)"
)

_PRECEDENCE = {
    "||": 1, "^^": 2, "&&": 3,
    "=": 4, "==": 4, "!=": 4, "<>": 4, "<": 4, "<=": 4,
    ">": 4, ">=": 4, "<=>": 4,
    "|": 5, "^": 6, "&": 7,
    "<<": 8, "<<<": 8, ">>": 8, ">>>": 8,
    "+": 9, "-": 9,
    "*": 10, "/": 10, "//": 10, "%": 10, "%%": 10,
}


def _number(token: str, *, dollarhex: bool = True) -> int | None:
    s = token.replace("_", "")
    if not s: return None
    try:
        if (dollarhex and s.startswith("$") and len(s) > 1 and s[1].isdigit() and
                all(c in "0123456789abcdefABCDEF" for c in s[1:])):
            return int(s[1:], 16)
        prefix_bases = {"x": 16, "h": 16, "b": 2, "y": 2,
                        "o": 8, "q": 8, "d": 10, "t": 10}
        suffix_bases = {"x": 16, "h": 16, "b": 2, "y": 2,
                        "o": 8, "q": 8, "d": 10, "t": 10}
        if len(s) >= 2 and s[0] == "0" and s[1].lower() in prefix_bases:
            base = prefix_bases[s[1].lower()]
            digits = s[2:] or "0"
            if all(c.lower() in "0123456789abcdef"[:base] for c in digits):
                return int(digits, base)
        if len(s) >= 2 and s[-1].lower() in suffix_bases and s[0].isdigit():
            base = suffix_bases[s[-1].lower()]
            digits = s[:-1]
            if all(c.lower() in "0123456789abcdef"[:base] for c in digits):
                return int(digits, base)
        if s.isdecimal():
            return int(s)
    except ValueError:
        raise ExpressionError(f"invalid number {token!r}") from None
    if s[0].isdigit():
        raise ExpressionError(f"invalid number {token!r}")
    return None


@dataclass(frozen=True)
class Value:
    number: int
    unresolved: bool = False
    symbolic: bool = False
    section: str | None = None
    relocation: int = 0
    # Optimizer provenance is not part of the public numeric Value identity.
    layout: Layout = field(default=(), compare=False, repr=False)
    forward: bool = field(default=False, compare=False, repr=False)
    # Section identity survives even when an expression is non-affine in
    # source positions. None derives bases from a newly constructed label's
    # layout; computed expressions carry an explicit (possibly empty) vector.
    bases: tuple[tuple[str, int], ...] | None = field(default=None, compare=False, repr=False)


def string_bytes(token: str) -> bytes:
    if len(token) < 2 or token[-1] != token[0] or token[0] not in "'\"`":
        raise ExpressionError("invalid string literal")
    if token[0] == "`":
        try:
            return unquote_backtick(token[1:-1].encode("latin-1"))
        except (UnicodeError, ValueError) as exc:
            raise ExpressionError(f"invalid string escape: {exc}") from exc
    return token[1:-1].encode("latin-1")


def _apply(op: str, a: int, b: int) -> int:
    def u64(value: int) -> int: return value & 0xFFFFFFFFFFFFFFFF
    def s64(value: int) -> int:
        value = u64(value)
        return value - 0x10000000000000000 if value & 0x8000000000000000 else value
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/":
        if u64(b) == 0: raise ExpressionError("division by zero")
        return u64(a) // u64(b)
    if op == "//":
        if u64(b) == 0: raise ExpressionError("division by zero")
        a, b = s64(a), s64(b)
        return (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
    if op == "%":
        if u64(b) == 0: raise ExpressionError("division by zero")
        return u64(a) % u64(b)
    if op == "%%":
        if u64(b) == 0: raise ExpressionError("division by zero")
        return s64(a) - _apply("//", a, b) * s64(b)
    if op in ("<<", "<<<"): return u64(a << (b & 63))
    if op == ">>": return u64(a) >> (b & 63)
    if op == ">>>": return s64(a) >> (b & 63)
    if op == "&": return a & b
    if op == "|": return a | b
    if op == "^": return a ^ b
    if op in ("=", "=="): return int(u64(a) == u64(b))
    if op in ("!=", "<>"): return int(u64(a) != u64(b))
    # NASM tests the signed 64-bit difference, which can itself wrap.
    difference = s64(a - b)
    if op == "<": return int(difference < 0)
    if op == "<=": return int(difference <= 0)
    if op == ">": return int(difference > 0)
    if op == ">=": return int(difference >= 0)
    if op == "<=>": return int(difference > 0)
    if op == "&&": return int(bool(u64(a)) and bool(u64(b)))
    if op == "||": return int(bool(u64(a)) or bool(u64(b)))
    if op == "^^": return int(bool(u64(a)) != bool(u64(b)))
    raise ExpressionError(f"unknown operator {op}")



def _relocation(op: str, a: Value, b: Value) -> int:
    """Combine section-base coefficients separately from numeric values."""
    if op == "+":
        return a.relocation + b.relocation
    if op == "-":
        return a.relocation - b.relocation
    if op == "*":
        if a.relocation and b.relocation:
            raise ExpressionError("unable to multiply two non-scalar objects")
        return a.relocation * b.number + b.relocation * a.number
    return 0


def _require_simple_relocation(value: Value) -> None:
    # Intermediate products may have any coefficient and cancel later, but
    # a complete operand/EQU/data expression must be simple or relocatable.
    if not value.unresolved and value.relocation not in (-1, 0, 1):
        raise ExpressionError("expression is not simple or relocatable")


def _bases(value: Value) -> tuple[tuple[str, int], ...]:
    if value.bases is not None:
        return value.bases
    terms: dict[str, int] = {}
    for section, _, coefficient in value.layout or ():
        terms[section] = terms.get(section, 0) + coefficient
    return tuple((section, coefficient) for section, coefficient in sorted(terms.items())
                 if coefficient)


def _combine_bases(op: str, a: Value, b: Value) -> tuple[tuple[str, int], ...]:
    if op not in ('+', '-', '*'):
        return ()
    terms: dict[str, int] = {}
    factors = (b.number, a.number) if op == '*' else (1, -1 if op == '-' else 1)
    for value, factor in zip((a, b), factors):
        for section, coefficient in _bases(value):
            terms[section] = terms.get(section, 0) + coefficient * factor
    return tuple((section, coefficient) for section, coefficient in sorted(terms.items())
                 if coefficient)


def _unary_bases(op: str, value: Value) -> tuple[tuple[str, int], ...]:
    if op == '+':
        return _bases(value)
    if op == '-':
        return tuple((section, -coefficient) for section, coefficient in _bases(value))
    return ()


def _is_scalar(value: Value) -> bool:
    return not value.relocation and not _bases(value)


def _require_scalar(value: Value) -> None:
    if not value.unresolved and not _is_scalar(value):
        raise ExpressionError("operator may only be applied to scalar values")


_COMPARISONS = frozenset(('=', '==', '!=', '<>', '<', '<=', '>', '>=', '<=>'))


def _binary_number(op: str, a: Value, b: Value, strict_scalars: bool, *,
                   different_registers: bool = False) -> int:
    if strict_scalars and op in _COMPARISONS:
        if a.unresolved or b.unresolved:
            return 0
        # NASM compares expression vectors, not just their current addresses.
        # Equality permits a non-scalar difference (which is unequal), while
        # ordered comparisons require the section/register terms to cancel.
        difference = Value(a.number - b.number,
                           relocation=a.relocation - b.relocation,
                           layout=combine_layout('-', a.layout, b.layout,
                                                 a.number, b.number),
                           bases=_combine_bases('-', a, b))
        if different_registers or not _is_scalar(difference):
            if op in ('=', '=='):
                return 0
            if op in ('!=', '<>'):
                return 1
            raise ExpressionError(f"'{op}': operands differ by a non-scalar")
    if strict_scalars and op in (
            '/', '//', '%', '%%', '<<', '<<<', '>>', '>>>',
            '&', '|', '^', '&&', '||', '^^'):
        _require_scalar(a)
        _require_scalar(b)
        # Unknown denominators are not zero denominators. Keep the unresolved
        # obligation so later passes resolve or refuse it; known zero still
        # reaches _apply and fails, even when the numerator is unknown.
        if op in ('/', '//', '%', '%%') and b.unresolved:
            return 0
    return _apply(op, a.number, b.number)


def evaluate(source: str, lookup: Callable[[str], Value], location: int | Value = 0,
             functions: Callable[[str, Value], Value | None] | None = None, *,
             allow_trailing: bool = False, dollarhex: bool = True,
             strict_scalars: bool = False) -> Value:
    """Evaluate one expression, optionally allowing unconsumed source text."""
    return _evaluate(source, lookup, location, functions,
                     allow_trailing=allow_trailing, dollarhex=dollarhex,
                     strict_scalars=strict_scalars)[0]


def evaluate_prefix(source: str, lookup: Callable[[str], Value], location: int | Value = 0,
                    functions: Callable[[str, Value], Value | None] | None = None, *,
                    dollarhex: bool = True, strict_scalars: bool = False) -> tuple[Value, int]:
    """Return the expression value and character offset immediately after it."""
    return _evaluate(source, lookup, location, functions, allow_trailing=True,
                     dollarhex=dollarhex, strict_scalars=strict_scalars)


def _evaluate(source: str, lookup: Callable[[str], Value], location: int | Value = 0,
             functions: Callable[[str, Value], Value | None] | None = None, *,
             allow_trailing: bool = False, dollarhex: bool = True,
             strict_scalars: bool = False) -> tuple[Value, int]:
    tokens: list[str] = []
    token_ends: list[int] = []
    pos = 0
    while pos < len(source):
        if source[pos:].isspace(): break
        match = _TOKEN.match(source, pos)
        if not match:
            if allow_trailing and tokens:
                break
            raise ExpressionError(f"invalid expression near {source[pos:]!r}")
        tokens.append(match.group(1))
        token_ends.append(match.end())
        pos = match.end()
    index = 0

    def parse(min_precedence: int = 0) -> Value:
        nonlocal index
        if index >= len(tokens): raise ExpressionError("expected expression")
        token = tokens[index]
        index += 1
        if token in ("+", "-", "~", "!"):
            child = parse(11)
            if strict_scalars and token in ('~', '!'):
                _require_scalar(child)
            number = child.number
            left = Value({"+": number, "-": -number, "~": ~number,
                          "!": int(not (number & 0xFFFFFFFFFFFFFFFF))}[token],
                         child.unresolved, child.symbolic, child.section,
                         child.relocation if token == "+" else (-child.relocation if token == "-" else 0),
                         child.layout if token == "+" else
                         scale_layout(child.layout, -1) if token in ("-", "~") else
                         (() if child.layout == () else None), child.forward,
                         bases=_unary_bases(token, child))
        elif token == "(":
            left = parse()
            if index >= len(tokens) or tokens[index] != ")": raise ExpressionError("missing ')'")
            index += 1
        elif token == "$":
            left = location if isinstance(location, Value) else Value(location, relocation=1)
        elif token == "$$":
            left = lookup("$$")
        elif token[0] in "'\"`":
            content = string_bytes(token)
            left = Value(int.from_bytes(content, "little"))
        else:
            numeric_token = _number(token, dollarhex=dollarhex)
            if (numeric_token is None and functions is not None and
                    index < len(tokens) and tokens[index] == "("):
                index += 1
                argument = parse()
                if index >= len(tokens) or tokens[index] != ")":
                    raise ExpressionError("missing ')' in function call")
                index += 1
                left = functions(token, argument)
                if left is None: raise ExpressionError(f"unknown function {token}")
                if argument.layout != ():
                    left = replace(left, layout=None, forward=argument.forward)
            else:
                left = Value(numeric_token) if numeric_token is not None else lookup(token)
        while index < len(tokens):
            op = tokens[index]
            if op == "?" and min_precedence == 0:
                if strict_scalars:
                    _require_scalar(left)
                index += 1
                when_true = parse(0)
                if index >= len(tokens) or tokens[index] != ":":
                    raise ExpressionError("missing ':' in conditional expression")
                index += 1
                when_false = parse(0)
                if left.unresolved:
                    left = Value(0, True, layout=None)
                else:
                    chosen = when_true if left.number & 0xFFFFFFFFFFFFFFFF else when_false
                    left = Value(chosen.number,
                                 when_true.unresolved or when_false.unresolved,
                                 chosen.symbolic, chosen.section, chosen.relocation,
                                 chosen.layout if left.layout == () else None,
                                 left.forward or when_true.forward or when_false.forward,
                                 bases=_bases(chosen))
                continue
            precedence = _PRECEDENCE.get(op, -1)
            if precedence < min_precedence: break
            index += 1
            right = parse(precedence + 1)
            section = left.section if right.section is None else (right.section if left.section is None else None)
            unknown_comparison = (op == "<=>" and
                                  bool((left.number - right.number) & 0x8000000000000000))
            left = Value(_binary_number(op, left, right, strict_scalars),
                         left.unresolved or right.unresolved or unknown_comparison,
                         left.symbolic or right.symbolic,
                         section, _relocation(op, left, right),
                         combine_layout(op, left.layout, right.layout,
                                        left.number, right.number),
                         left.forward or right.forward,
                         bases=_combine_bases(op, left, right))
        return left

    result = parse()
    if not allow_trailing and index != len(tokens):
        raise ExpressionError(f"unexpected token {tokens[index]!r}")
    _require_simple_relocation(result)
    return result, token_ends[index - 1]


def evaluate_address(source: str, lookup: Callable[[str], Value], location: int | Value = 0,
                     functions: Callable[[str, Value], Value | None] | None = None, *,
                     strict_scalars: bool = False
                     ) -> tuple[Value, dict[str, int]]:
    """Evaluate a linear 8086 address, retaining register coefficients."""
    registers = frozenset("ax cx dx bx sp bp si di".split())
    tokens: list[str] = []
    pos = 0
    while pos < len(source):
        if source[pos:].isspace(): break
        match = _TOKEN.match(source, pos)
        if not match: raise ExpressionError(f"invalid expression near {source[pos:]!r}")
        tokens.append(match.group(1))
        pos = match.end()
    index = 0

    def parse(min_precedence: int = 0) -> tuple[Value, dict[str, int]]:
        nonlocal index
        if index >= len(tokens): raise ExpressionError("expected expression")
        token = tokens[index]
        index += 1
        if token in ("+", "-", "~", "!"):
            value, coeffs = parse(11)
            if token in ("~", "!") and coeffs:
                raise ExpressionError("nonlinear effective address")
            if strict_scalars and token in ('~', '!'):
                _require_scalar(value)
            number = {"+": value.number, "-": -value.number,
                      "~": ~value.number,
                      "!": int(not (value.number & 0xFFFFFFFFFFFFFFFF))}[token]
            left = (Value(number, value.unresolved, value.symbolic, value.section,
                          value.relocation if token == "+" else
                          (-value.relocation if token == "-" else 0),
                          value.layout if token == "+" else
                          scale_layout(value.layout, -1) if token in ("-", "~") else
                          (() if value.layout == () else None), value.forward,
                          bases=_unary_bases(token, value)),
                    {reg: coefficient * (-1 if token == "-" else 1)
                     for reg, coefficient in coeffs.items()})
        elif token == "(":
            left = parse()
            if index >= len(tokens) or tokens[index] != ")":
                raise ExpressionError("missing ')'")
            index += 1
        elif token == "$":
            left = (location if isinstance(location, Value) else
                    Value(location, relocation=1)), {}
        elif token == "$$":
            left = lookup("$$"), {}
        elif token[0] in "'\"`":
            left = Value(int.from_bytes(string_bytes(token), "little")), {}
        elif token.lower() in registers:
            left = Value(0), {token.lower(): 1}
        else:
            if functions is not None and index < len(tokens) and tokens[index] == "(":
                index += 1
                argument, coefficients = parse()
                if coefficients:
                    raise ExpressionError("nonlinear effective address")
                if index >= len(tokens) or tokens[index] != ")":
                    raise ExpressionError("missing ')' in function call")
                index += 1
                value = functions(token, argument)
                if value is None: raise ExpressionError(f"unknown function {token}")
                left = value, {}
            else:
                n = _number(token)
                left = (Value(n) if n is not None else lookup(token)), {}
        while index < len(tokens):
            op = tokens[index]
            if op == "?" and min_precedence == 0:
                if strict_scalars:
                    _require_scalar(left[0])
                index += 1
                when_true = parse()
                if index >= len(tokens) or tokens[index] != ":":
                    raise ExpressionError("missing ':' in conditional expression")
                index += 1
                when_false = parse()
                if left[1]:
                    raise ExpressionError("nonlinear effective address")
                if left[0].unresolved:
                    left = Value(0, True), {}
                else:
                    left = when_true if left[0].number & 0xFFFFFFFFFFFFFFFF else when_false
                continue
            precedence = _PRECEDENCE.get(op, -1)
            if precedence < min_precedence: break
            index += 1
            right = parse(precedence + 1)
            a, ac = left
            b, bc = right
            section = a.section if b.section is None else (b.section if a.section is None else None)
            if op in ("+", "-"):
                sign = 1 if op == "+" else -1
                coefficients = ac.copy()
                for reg, coefficient in bc.items():
                    coefficients[reg] = coefficients.get(reg, 0) + sign * coefficient
                coefficients = {reg: coefficient for reg, coefficient in coefficients.items()
                                if coefficient}
                relocation = a.relocation + sign * b.relocation
            elif op == "*":
                if ((ac or a.relocation) and (bc or b.relocation) or
                        (ac and b.unresolved) or (bc and a.unresolved)):
                    raise ExpressionError("nonlinear effective address")
                coefficients = ({reg: coefficient * b.number for reg, coefficient in ac.items()}
                                if ac else {reg: coefficient * a.number for reg, coefficient in bc.items()})
                coefficients = {reg: coefficient for reg, coefficient in coefficients.items()
                                if coefficient}
                relocation = _relocation(op, a, b)
            elif strict_scalars and op in _COMPARISONS:
                # A comparison consumes register terms rather than encoding
                # them in the final address. Equal vectors may cancel.
                coefficients = {}
                relocation = 0
            else:
                if ac or bc:
                    raise ExpressionError("nonlinear effective address")
                coefficients = {}
                relocation = 0
            unknown_comparison = (op == "<=>" and
                                  bool((a.number - b.number) & 0x8000000000000000))
            left = (Value(_binary_number(op, a, b, strict_scalars,
                                        different_registers=ac != bc),
                          a.unresolved or b.unresolved or unknown_comparison,
                          a.symbolic or b.symbolic, section, relocation,
                          combine_layout(op, a.layout, b.layout, a.number, b.number),
                          a.forward or b.forward,
                          bases=_combine_bases(op, a, b)), coefficients)
        return left

    result = parse()
    if index != len(tokens): raise ExpressionError(f"unexpected token {tokens[index]!r}")
    _require_simple_relocation(result[0])
    return result
