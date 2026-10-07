"""Lossless, conservative numeric lexer: formatting never suppresses a number.

Offsets refer to original Unicode text. Ambiguous/unsupported syntax raises;
callers must resolve it rather than silently omit a substantive occurrence.
"""

import re
from datetime import date
from decimal import Decimal
from html import unescape

from cre_brain.gates.models import NumberToken

_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_SCALES = {"k": 3, "thousand": 3, "m": 6, "mm": 6, "million": 6, "b": 9, "bn": 9, "billion": 9}
_CURRENCY = r"USD|EUR|GBP|JPY|CAD|AUD|CHF|US\$|C\$|A\$|[$€£¥]"
_MARKUP = r"(?:[*_`~]|<[^>]*>)"
_SPLIT_MARKUP = r"(?:[*_`~\[\]!(){}\\]|<[^>]*>)"
# Space/apostrophe/comma grouping is retained for validation below.
_NUM = r"(?:\d+(?:[, '\u00a0\u202f]\d+)*\.\d+|\d+(?:[, '\u00a0\u202f]\d+)*|\.\d+)(?:[eE][+\-]?\d+)?"
_TOKEN = re.compile(
    r"[ \t]*(?P<date>\d{4}-\d{2}-\d{2})(?!\d)|"
    rf"(?P<open>\()?[ \t]*(?P<sign>[+\-−])?[ \t]*(?P<currency>{_CURRENCY})?[ \t]*"
    rf"(?P<sign2>[+\-−])?[ \t]*(?P<number>{_NUM})"
    rf"(?P<scale>[ \t]*(?:thousand|million|billion|mm|bn|k|m|b)\b)?"
    rf"(?P<suffix>[ \t]*(?:%|percent\b|bps\b|{_CURRENCY}))?[ \t]*(?P<close>\))?",
    re.IGNORECASE,
)


def _decimal(raw: str, shift: int, negative: bool) -> Decimal:
    scientific = re.split("[eE]", raw)
    exponent = int(scientific[1]) if len(scientific) == 2 else 0
    body = scientific[0]
    integer, dot, decimals = body.partition(".")
    groups = re.split("[, '\u00a0\u202f]", integer)
    if len(groups) > 1 and (not 1 <= len(groups[0]) <= 3 or any(len(g) != 3 for g in groups[1:])):
        raise ValueError("Malformed or ambiguous numeric grouping")
    digits = "".join(groups) + decimals
    if len(digits) > 4096 or abs(exponent + shift - len(decimals)) > 4096:
        raise ValueError("Numeric display exceeds exact arithmetic budget")
    return Decimal((int(negative), tuple(int(d) for d in digits), exponent + shift - len(decimals)))


def _currency(raw: str) -> str:
    return {**_CURRENCIES, "US$": "USD", "C$": "CAD", "A$": "AUD"}.get(raw.upper(), raw.upper())


def _column_heading(text: str, position: int) -> str | None:
    line_start = text.rfind("\n", 0, position) + 1
    line_end = text.find("\n", position)
    line = text[line_start : line_end if line_end >= 0 else len(text)]
    if "|" not in line:
        return None
    column = text[line_start:position].count("|")
    prior = text[:line_start].splitlines()
    for index in range(len(prior) - 1, 0, -1):
        if re.fullmatch(r"[\s|:\-]+", prior[index]) and "|" in prior[index - 1]:
            headings = prior[index - 1].split("|")
            return headings[column] if column < len(headings) else None
    return None


def _header_unit(heading: str | None) -> tuple[str, int, str] | None:
    if heading is None:
        return None
    if re.search(r"[$€£¥]\s*0{2,}|\b(?:USD|EUR|GBP)\s*0{2,}", heading, re.I):
        raise ValueError("Numeric table header scaling is unsupported")
    money = re.search(
        rf"(?P<currency>{_CURRENCY})[ \t]*(?P<scale>thousand|million|billion|mm|bn|k|m|b)?"
        r"(?P<dimension>/(?:month|year|unit|sqft))?",
        heading,
        re.I,
    )
    percent = re.search(r"%|\bpercent\b|\bbps\b", heading, re.I)
    if money and percent:
        raise ValueError("Conflicting table header display units")
    if percent:
        return "ratio", (-4 if percent[0].lower() == "bps" else -2), percent[0]
    if money:
        unit = _currency(money["currency"]) + (money["dimension"] or "").lower()
        scale = (money["scale"] or "").lower()
        return unit, _SCALES.get(scale, 0), scale or money["currency"]
    return None


def extract_numbers(text: str) -> tuple[NumberToken, ...]:
    if unescape(text) != text or re.search(
        rf"\d(?:{_MARKUP})+\d|"
        rf"(?:{_CURRENCY}|[+−\-])(?:\s*{_SPLIT_MARKUP})+\s*(?:{_CURRENCY})?\s*\d|"
        rf"\((?:\s*{_SPLIT_MARKUP})+\s*(?:{_CURRENCY})?\s*\d|"
        rf"\d(?:\s*{_MARKUP})+\s*%",
        text,
        re.I,
    ):
        raise ValueError("Encoded or split numeric display is unsupported; use a literal display")
    if re.search(
        r"\d\.\.\d|%%|\b(?:nan|infinity|inf)\b|[∞]|\b0[xob][0-9a-f]+|\d\s*/\s*\d", text, re.I
    ):
        raise ValueError("Nonfinite or unsupported numeric notation")
    tokens: list[NumberToken] = []
    shifts: list[int] = []
    consumed: set[int] = set()
    for match in _TOKEN.finditer(text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if match["date"]:
            parsed = date.fromisoformat(match["date"])
            tokens.append(
                NumberToken(
                    start=start,
                    end=end,
                    raw=text[start:end],
                    value=Decimal(parsed.strftime("%Y%m%d")),
                    unit="date",
                    display_unit="ISO date",
                    date_value=parsed,
                )
            )
            shifts.append(0)
            consumed.update(i for i in range(start, end) if text[i].isdigit())
            continue
        currency = (match["currency"] or "").strip()
        suffix = (match["suffix"] or "").strip()
        suffix_lower = suffix.lower()
        scale = (match["scale"] or "").strip().lower()
        negative = (match["sign"] or match["sign2"]) in {"-", "−"}
        if match["sign"] and match["sign2"]:
            raise ValueError("Ambiguous numeric signs")
        # Hyphens between successive numbers are ranges, including a suffix scale.
        range_pair = bool(tokens and re.fullmatch(r"\s*[–—\-]\s*", text[tokens[-1].end : start]))
        if negative and tokens and re.fullmatch(r"\s*", text[tokens[-1].end : start]):
            if text[start] == "-":
                range_pair = True
                negative = False
                start += 1
        accounting = bool(match["open"] and match["close"])
        if accounting and negative:
            raise ValueError("Accounting display has conflicting signs")
        negative |= accounting
        shift = _SCALES.get(scale, 0)
        unit = _currency(currency) if currency else "number"
        if suffix_lower in {"%", "percent", "bps"}:
            if currency or scale:
                raise ValueError("Mixed monetary and percentage display units")
            unit = "ratio"
            shift = -4 if suffix_lower == "bps" else -2
        elif suffix:
            suffix_currency = _currency(suffix)
            if currency and suffix_currency != unit:
                raise ValueError("Conflicting currency display units")
            unit = suffix_currency
        dimension = re.match(
            r"[ \t]*(/(?:month|year|unit|sqft)\b|(?:sqft|days?|years?|units?)\b)", text[end:], re.I
        )
        if dimension:
            dimension_word = dimension[1].lower()
            if dimension_word.startswith("/"):
                if unit not in _CURRENCIES.values() and unit not in {"CAD", "AUD", "CHF"}:
                    raise ValueError("Dimensional money requires a currency")
                unit += dimension_word
            else:
                if unit != "number":
                    raise ValueError("Incompatible numeric display dimensions")
                unit = {
                    "day": "days",
                    "days": "days",
                    "year": "year",
                    "years": "year",
                    "unit": "count",
                    "units": "count",
                    "sqft": "sqft",
                }[dimension_word]
            end += dimension.end()
        header = _header_unit(_column_heading(text, start))
        if header:
            header_unit, header_shift, header_display = header
            header_currency = header_unit.split("/", maxsplit=1)[0]
            if unit != "number" and unit != header_unit and unit != header_currency:
                raise ValueError("Cell display unit disagrees with its table column")
            if unit == "number":
                unit = header_unit
                if scale and header_shift:
                    raise ValueError("Cell and table header specify conflicting numeric scales")
                if not scale:
                    shift = header_shift
                if not scale and header_shift > 0:
                    scale = header_display.lower()
            elif currency and not scale:
                unit = header_unit
                shift = header_shift
                if header_shift > 0:
                    scale = header_display.lower()
        else:
            header_display = ""
        if range_pair and tokens:
            previous = tokens[-1]
            if unit == "number" and previous.unit != "number":
                unit = previous.unit
                if unit == "ratio":
                    shift = -4 if previous.display_unit.lower() == "bps" else -2
            elif unit != "number" and previous.unit != "number" and unit != previous.unit:
                raise ValueError("Conflicting units in numeric range")
            if not scale and previous.display_unit.lower() in _SCALES:
                shift = _SCALES[previous.display_unit.lower()]
            if (scale and previous.display_unit.lower() not in _SCALES) or (
                previous.unit == "number" and unit != "number"
            ):
                sign, digits, exponent = previous.value.as_tuple()
                assert isinstance(exponent, int)
                tokens[-1] = previous.model_copy(
                    update={
                        "unit": unit,
                        "display_unit": suffix or scale or currency or unit,
                        "value": Decimal((sign, digits, exponent + shift - shifts[-1])),
                    }
                )
                shifts[-1] = shift
        following = text[end:]
        word = re.match(r"[ \t]*([A-Za-z]+)\b", following)
        # Unrecognized immediate unit words are unresolved. Ordinary connecting
        # prose is permitted; punctuation/newlines terminate the display.
        if (
            word
            and word[1].lower()
            not in {
                "and",
                "or",
                "to",
                "at",
                "in",
                "on",
                "as",
                "is",
                "was",
                "were",
                "with",
                "for",
                "from",
                "of",
                "per",
                "a",
                "an",
                "the",
                "by",
                "but",
                "than",
                "through",
            }
        ) or following.startswith("/"):
            raise ValueError("Unsupported or ambiguous display unit")
        token = NumberToken(
            start=start,
            end=end,
            raw=text[start:end],
            value=_decimal(match["number"], shift, negative),
            unit=unit,
            display_unit=scale or suffix or currency or header_display or "number",
        )
        tokens.append(token)
        shifts.append(shift)
        consumed.update(i for i in range(start, end) if text[i].isdigit())
        # Known substantive unit words are validated, never ignored.
        following = text[end:]
        if re.match(r"\s*(?:bitcoins?|btc|eth|satoshis?|crore|lakh|trillion)\b", following, re.I):
            raise ValueError("Unsupported display unit")
    if any(char.isdigit() and index not in consumed for index, char in enumerate(text)):
        raise ValueError("Unsupported numeric characters/notation")
    return tuple(tokens)


def number_context(text: str, token: NumberToken) -> str:
    """Current prose line/table cell plus its corresponding table column heading."""
    line_start = text.rfind("\n", 0, token.start) + 1
    line_end = text.find("\n", token.end)
    line = text[line_start : line_end if line_end >= 0 else len(text)]
    if "|" in line:
        column = text[line_start : token.start].count("|")
        cells = line.split("|")
        context = cells[column] if column < len(cells) else ""
        prior = text[:line_start].splitlines()
        for index in range(len(prior) - 1, 0, -1):
            if re.fullmatch(r"[\s|:\-]+", prior[index]) and "|" in prior[index - 1]:
                headings = prior[index - 1].split("|")
                if column < len(headings):
                    context += " " + headings[column]
                break
        return context
    separators = list(
        re.finditer(r"[.!?](?=\s|$)|;|,\s+|\b(?:and|versus|vs|while|but)\b", line, re.I)
    )
    position = token.start - line_start
    left = max((m.end() for m in separators if m.end() <= position), default=0)
    right = min(
        (m.start() for m in separators if m.start() >= token.end - line_start), default=len(line)
    )
    return line[left:right]


def has_label(text: str, label: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"[^\w]+", " ", value.casefold()).strip()

    return bool(normalize(label)) and f" {normalize(label)} " in f" {normalize(text)} "
