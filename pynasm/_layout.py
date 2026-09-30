"""Affine dependencies on source positions, separate from object relocations.

Each term is (section, expanded-source line index, coefficient).  An empty
tuple is constant; None means a non-affine/unknown dependency.  In particular,
a label difference can have relocation zero but still change during layout.
"""
from __future__ import annotations

Layout = tuple[tuple[str, int, int], ...] | None


def scale_layout(terms: Layout, factor: int) -> Layout:
    if factor == 0:
        return ()
    if terms is None:
        return None
    return tuple((section, line, coefficient * factor)
                 for section, line, coefficient in terms)


def combine_layout(op: str, a: Layout, b: Layout, av: int, bv: int) -> Layout:
    if op == "*":
        if a == ():
            return scale_layout(b, av)
        if b == ():
            return scale_layout(a, bv)
    if a is None or b is None:
        return None
    if not a and not b:
        return ()
    if op not in ("+", "-"):
        return None
    terms: dict[tuple[str, int], int] = {}
    for group, sign in ((a, 1), (b, 1 if op == "+" else -1)):
        for section, line, coefficient in group:
            key = section, line
            terms[key] = terms.get(key, 0) + sign * coefficient
    return tuple((section, line, coefficient)
                 for (section, line), coefficient in sorted(terms.items())
                 if coefficient)
