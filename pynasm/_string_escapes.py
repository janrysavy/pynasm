"""Byte-oriented NASM backquote escapes (not Python's unicode_escape codec)."""


def _utf8(value: int) -> bytes:
    # NASM's escape encoder preserves its historical 1..6-byte UTF-8 form,
    # including surrogate values and the full 32-bit range of a \U escape.
    if value < 0x80:
        return bytes((value,))
    for size, limit, prefix in ((2, 0x800, 0xC0), (3, 0x10000, 0xE0),
                                (4, 0x200000, 0xF0), (5, 0x4000000, 0xF8),
                                (6, 0x100000000, 0xFC)):
        if value < limit:
            return bytes((prefix + (value >> (6 * (size - 1))),)) + bytes(
                0x80 | ((value >> shift) & 63)
                for shift in range(6 * (size - 2), -1, -6))
    raise ValueError("escape value exceeds 32 bits")


def unquote_backtick(content: bytes) -> bytes:
    """Decode the contents of a backquoted literal, preserving arbitrary bytes."""
    simple = dict(zip(b"abefnrtv", (7, 8, 27, 12, 10, 13, 9, 11)))
    numeric = {ord("x"): (16, 2), ord("X"): (16, 2),
               ord("u"): (16, 4), ord("U"): (16, 8),
               ord("d"): (10, 3), ord("o"): (8, 3)}
    digits = b"0123456789abcdef"
    result = bytearray()
    index = 0
    while index < len(content):
        char = content[index]
        index += 1
        if char != 92 or index == len(content):
            result.append(char)
            continue
        start = index
        escape = content[index]
        index += 1
        if escape in simple:
            result.append(simple[escape])
            continue
        if escape == ord("^") and index < len(content):
            char = content[index]
            index += 1
            result.append(127 if char == ord("?") else char & 0x9F)
            continue
        if ord("0") <= escape <= ord("7"):
            base, maximum = 8, 3
            index = start  # The first octal digit is part of the number.
        elif escape in numeric:
            base, maximum = numeric[escape]
        else:
            result.append(escape)  # Unknown escapes discard the backslash.
            continue
        braced = index < len(content) and content[index] == ord("{")
        if braced:
            index += 1
        number_start = index
        value = 0
        while index < len(content) and (braced or index - number_start < maximum):
            digit = digits.find(bytes((content[index],)).lower())
            if digit < 0 or digit >= base:
                break
            # Only the low 32 bits can affect NASM's eventual byte/UTF-8 output.
            value = (value * base + digit) & 0xFFFFFFFF
            index += 1
        if braced:
            if index == len(content) or content[index] != ord("}"):
                index = start  # Replay malformed sequences without the slash.
                continue
            index += 1
        elif index == number_start:
            index = start
            continue
        if escape in (ord("u"), ord("U")):
            result.extend(_utf8(value))
        else:
            result.append(value & 255)
    return bytes(result)
