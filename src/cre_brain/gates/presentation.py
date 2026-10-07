"""Conservative visible Markdown and exact supported Excel display semantics."""

import re
from decimal import Decimal
from fractions import Fraction

from cre_brain.gates.limits import GateFailure, bounded_decimal


def visible_text(text: str) -> str:
    """Mask invisible/unsupported regions without moving citation offsets."""

    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if c == "\n" else " " for c in match[0])

    text = re.sub(r"<!--.*?(?:-->|$)", mask, text, flags=re.S)
    # HTML layout can hide content or alter units. Require plain Markdown.
    if re.search(r"</?[A-Za-z][^>]*>", text):
        raise GateFailure("unsupported_display")
    return text


def displayed_decimal(value: Decimal, fmt: str, unit: str) -> Decimal:
    bounded_decimal(value)
    match = re.fullmatch(r"0(?:\.(0+))?(%)?", fmt)
    if match is None or (match[2] and unit != "ratio"):
        raise GateFailure("unsupported_display")
    # Excel fixed-decimal displays round halves away from zero. Compute the
    # displayed quantity exactly, including percent scale, with no Decimal context.
    places = len(match[1] or "")
    shift = 2 if match[2] else 0
    scaled = abs(Fraction(value)) * 10 ** (places + shift)
    rounded = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    digits = tuple(int(c) for c in str(rounded))
    return Decimal((int(value < 0), digits, -places - shift))
