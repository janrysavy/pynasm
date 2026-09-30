"""Encode NASM floating data constants without native assembler dependencies."""

from __future__ import annotations

import re
from fractions import Fraction


_FORMATS = {
    1: (4, 3, 7),
    2: (5, 10, 15),
    4: (8, 23, 127),
    8: (11, 52, 1023),
    10: (15, 63, 16383),  # x87 stores the leading bit explicitly.
    16: (15, 112, 16383),
}
_OVERFLOW = object()
_UNDERFLOW = object()


def _round_ratio(numerator: int, denominator: int, *, mode: str = "near",
                 negative: bool = False) -> int:
    quotient, remainder = divmod(numerator, denominator)
    # NASM's ROUND_ABS_UP adds at the first discarded bit. If that bit is
    # clear, a directed round-up does not carry into the emitted field.
    if mode == "near":
        increment = (remainder * 2 > denominator or
                     (remainder * 2 == denominator and bool(quotient & 1)))
    elif mode == "zero":
        increment = False
    elif mode == "up":
        increment = not negative and remainder * 2 >= denominator
    elif mode == "down":
        increment = negative and remainder * 2 >= denominator
    else:
        raise ValueError("invalid floating-point rounding mode")
    return quotient + int(increment)


def _scaled_round(value: Fraction, shift: int, *, mode: str = "near",
                  negative: bool = False) -> int:
    if shift >= 0:
        return _round_ratio(value.numerator << shift, value.denominator,
                            mode=mode, negative=negative)
    return _round_ratio(value.numerator, value.denominator << -shift,
                        mode=mode, negative=negative)


def _binary_exponent(value: Fraction) -> int:
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    if exponent >= 0:
        if value.numerator < value.denominator << exponent:
            exponent -= 1
    elif value.numerator << -exponent < value.denominator:
        exponent -= 1
    return exponent


def _nasm_decimal_mantissa(token: str) -> tuple[int, int] | None:
    """NASM's 192-bit decimal intermediate, before IEEE-format rounding."""
    source = token.replace("_", "")
    if source.lower().startswith(("0d", "0t")):
        source = source[2:]
    match = re.fullmatch(r"(?i)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?", source)
    if match is None or (match.group(2) is None and match.group(3) is None):
        return None
    whole, fractional, power = match.groups()
    fractional = fractional or ""
    exponent = max(-5000, min(5000, int(power or 0)))
    whole_nonzero = next((index for index, char in enumerate(whole) if char != "0"), None)
    if whole_nonzero is not None:
        ten_power = len(whole) - whole_nonzero + exponent
        digits = (whole[whole_nonzero:] + fractional)[:52]
    else:
        fractional_nonzero = next((index for index, char in enumerate(fractional)
                                   if char != "0"), None)
        if fractional_nonzero is None:
            return 0, 0
        ten_power = -fractional_nonzero + exponent
        digits = fractional[fractional_nonzero:][:52]
    fraction = Fraction(int(digits), 10 ** len(digits))
    binary_power = _binary_exponent(fraction) + 1
    shift = 192 - binary_power
    mantissa = ((fraction.numerator << shift) // fraction.denominator if shift >= 0
                else fraction.numerator // (fraction.denominator << -shift))
    binary_power += ten_power

    def multiply(left: int, right: int) -> tuple[int, int]:
        product = left * right
        high = product >> 192
        if high & (1 << 191):
            return high, 0
        return (product >> 191) & ((1 << 192) - 1), -1

    if ten_power < 0:
        multiplier = int("cc" * 23 + "cd", 16)
        multiplier_power = -2
        ten_power = -ten_power
    elif ten_power > 0:
        multiplier = 5 << 189
        multiplier_power = 3
    else:
        multiplier = 0
        multiplier_power = 0
    while ten_power:
        if ten_power & 1:
            mantissa, delta = multiply(mantissa, multiplier)
            binary_power += multiplier_power + delta
        multiplier, delta = multiply(multiplier, multiplier)
        multiplier_power = multiplier_power * 2 + delta
        ten_power >>= 1
    return mantissa, binary_power


def _nasm_round_mantissa(mantissa: int, bits: int, *, mode: str,
                         negative: bool) -> int:
    shift = 192 - bits
    quotient, remainder = divmod(mantissa, 1 << shift)
    if mode == "near":
        increment = remainder * 2 > (1 << shift) or (remainder * 2 == (1 << shift)
                                                   and bool(quotient & 1))
    elif mode == "zero":
        increment = False
    elif mode == "up":
        increment = not negative and remainder >= (1 << (shift - 1))
    elif mode == "down":
        increment = negative and remainder >= (1 << (shift - 1))
    else:
        raise ValueError("invalid floating-point rounding mode")
    return ((quotient + int(increment)) << shift) & ((1 << 192) - 1)


def _encode_nasm_decimal(token: str, width: int, exponent_bits: int,
                         explicit: bool, *, rounding: str, daz: bool,
                         negative: bool) -> bytes | None:
    intermediate = _nasm_decimal_mantissa(token)
    if intermediate is None:
        return None
    mantissa, binary_power = intermediate
    exponent = binary_power - 1
    exponent_max = 1 << (exponent_bits - 1)
    significant_bit = 1 << (191 - exponent_bits - int(explicit))
    infinity = ((1 << exponent_bits) - 1) << (191 - exponent_bits)
    if explicit:
        infinity |= significant_bit
    if mantissa == 0:
        encoded = 0
    elif 2 - exponent_max <= exponent <= exponent_max:
        exponent_field = exponent + exponent_max - 1
        mantissa >>= exponent_bits + int(explicit)
        mantissa = _nasm_round_mantissa(mantissa, width * 8,
                                        mode=rounding, negative=negative)
        if mantissa & (significant_bit << 1):
            mantissa >>= 1
            exponent_field += 1
        if exponent_field >= (exponent_max << 1) - 1:
            encoded = infinity
        else:
            if not explicit:
                mantissa &= ~significant_bit
            encoded = mantissa | (exponent_field << (191 - exponent_bits))
    elif exponent > 0:
        encoded = infinity
    else:
        shift = -(exponent + exponent_max - 2 - exponent_bits) + int(explicit)
        mantissa = mantissa >> shift if shift < 192 else 0
        mantissa = _nasm_round_mantissa(mantissa, width * 8,
                                        mode=rounding, negative=negative)
        if mantissa & significant_bit:
            if not explicit:
                mantissa &= ~significant_bit
            encoded = mantissa | (1 << (191 - exponent_bits))
        else:
            encoded = 0 if daz else mantissa
    if negative:
        encoded |= 1 << 191
    return (encoded >> (192 - width * 8)).to_bytes(width, "little")


def _literal_value(token: str) -> Fraction | object | None:
    source = token.replace("_", "")
    if source.startswith("$"):
        source = "0x" + source[1:]
    prefixed = re.fullmatch(r"(?i)0([xhboyq])([0-9a-f]*)(?:\.([0-9a-f]*))?(?:p([+-]?\d+))?", source)
    if prefixed:
        marker, whole, fractional, exponent = prefixed.groups()
        if fractional is None and exponent is None:
            return None
        base = {"x": 16, "h": 16, "b": 2, "y": 2, "o": 8, "q": 8}[marker.lower()]
        digits = whole + (fractional or "")
        if not digits or any(int(digit, 16) >= base for digit in digits):
            raise ValueError("invalid floating-point constant")
        numerator = int(digits, base)
        if not numerator:
            return Fraction(0)
        power = int(exponent or 0)
        if numerator:
            bits_per_digit = {2: 1, 8: 3, 16: 4}[base]
            binary_order = numerator.bit_length() - 1 - len(fractional or "") * bits_per_digit + power
            if binary_order > 20000: return _OVERFLOW
            if binary_order < -20000: return _UNDERFLOW
        result = Fraction(numerator, base ** len(fractional or ""))
        return result * (1 << power) if power >= 0 else result / (1 << -power)
    if source.lower().startswith(("0d", "0t")):
        source = source[2:]
    decimal = re.fullmatch(r"(?i)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?", source)
    if decimal is None:
        return None
    whole, fractional, exponent = decimal.groups()
    if fractional is None and exponent is None:
        return None
    digits = whole + (fractional or "")
    power = int(exponent or 0) - len(fractional or "")
    significant = digits.lstrip("0")
    if not significant:
        return Fraction(0)
    if significant:
        decimal_order = len(significant) - 1 + power
        if decimal_order > 6000: return _OVERFLOW
        if decimal_order < -6000: return _UNDERFLOW
    result = Fraction(int(digits), 1)
    return result * (10 ** power) if power >= 0 else result / (10 ** -power)


def encode_float(token: str, width: int, *, bfloat: bool = False,
                 rounding: str = "near", daz: bool = False) -> bytes | None:
    """Return bytes for a whole floating literal, or None for a nonfloat token."""
    if width not in _FORMATS or (bfloat and width != 2):
        return None
    source = token.strip()
    sign = 0
    if source.startswith(("+", "-")):
        sign = int(source[0] == "-")
        source = source[1:].strip()
    exponent_bits, fraction_bits, bias = (8, 7, 127) if bfloat else _FORMATS[width]
    special = source.lower()
    if special in ("__infinity__", "__nan__", "__qnan__", "__snan__"):
        exponent_field = (1 << exponent_bits) - 1
        if special == "__infinity__": significand = (1 << fraction_bits) if width == 10 else 0
        elif special == "__snan__": significand = (1 << fraction_bits) + 1 if width == 10 else 1
        else: significand = ((1 << fraction_bits) + (1 << (fraction_bits - 1)) if width == 10
                             else 1 << (fraction_bits - 1))
    else:
        value = _literal_value(source)
        if value is None:
            return None
        if isinstance(value, Fraction) and value != 0:
            decimal = _encode_nasm_decimal(
                source, width, exponent_bits, width == 10 and not bfloat,
                rounding=rounding, daz=daz, negative=bool(sign))
            if decimal is not None:
                return decimal
        if value is _OVERFLOW:
            exponent_field = (1 << exponent_bits) - 1
            significand = (1 << fraction_bits) if width == 10 else 0
        elif value is _UNDERFLOW or value == 0:
            exponent_field = significand = 0
        else:
            exponent = _binary_exponent(value)
            maximum_field = (1 << exponent_bits) - 1
            if exponent + bias >= maximum_field:
                exponent_field = maximum_field
                significand = (1 << fraction_bits) if width == 10 else 0
            elif exponent + bias > 0:
                significand = _scaled_round(value, fraction_bits - exponent,
                                            mode=rounding, negative=bool(sign))
                if significand >= 1 << (fraction_bits + 1):
                    significand >>= 1
                    exponent += 1
                exponent_field = exponent + bias
                if exponent_field >= maximum_field:
                    exponent_field = maximum_field
                    significand = (1 << fraction_bits) if width == 10 else 0
                elif width != 10:
                    significand -= 1 << fraction_bits
            else:
                significand = _scaled_round(value, fraction_bits + bias - 1,
                                            mode=rounding, negative=bool(sign))
                if significand >= 1 << fraction_bits:
                    exponent_field = 1
                    significand = (1 << fraction_bits) if width == 10 else 0
                else:
                    exponent_field = 0
                    if daz:
                        significand = 0
    total_bits = width * 8
    encoded = (sign << (total_bits - 1)) | (exponent_field << (total_bits - 1 - exponent_bits)) | significand
    return encoded.to_bytes(width, "little")


def encode_bcd(token: str) -> bytes | None:
    """Encode an x87 packed-BCD literal, retaining its lowest 18 digits."""
    source = token.strip().replace("_", "")
    sign = 0
    if source.startswith(("+", "-")):
        sign = int(source[0] == "-")
        source = source[1:]
    match = re.fullmatch(r"(?i)(?:0p(\d+)|(\d+)p)", source)
    if not match:
        return None
    digits = (match.group(1) or match.group(2))[-18:].rjust(18, "0")
    value = int(digits)
    packed = bytearray(10)
    for index in range(9):
        value, pair = divmod(value, 100)
        packed[index] = (pair // 10 << 4) | (pair % 10)
    packed[9] = 0x80 if sign else 0
    return bytes(packed)


def float_operator(name: str, argument: str, *, rounding: str = "near",
                   daz: bool = False) -> int | None:
    """Evaluate a NASM float-to-integer preprocessor operator."""
    normalized = name.lower().replace("?", "")
    formats = {"__float8__": (1, False), "__float16__": (2, False),
               "__bfloat16__": (2, True), "__float32__": (4, False),
               "__float64__": (8, False), "__float80m__": (10, False),
               "__float80e__": (10, False), "__float128l__": (16, False),
               "__float128h__": (16, False)}
    if normalized not in formats:
        return None
    width, bfloat = formats[normalized]
    encoded = encode_float(argument, width, bfloat=bfloat,
                           rounding=rounding, daz=daz)
    if encoded is None:
        raise ValueError("invalid floating-point constant")
    if normalized == "__float80m__": encoded = encoded[:8]
    elif normalized == "__float80e__": encoded = encoded[8:]
    elif normalized == "__float128l__": encoded = encoded[:8]
    elif normalized == "__float128h__": encoded = encoded[8:]
    return int.from_bytes(encoded, "little")
