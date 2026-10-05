"""Resolve semantic selections against exact authenticated immutable observations."""

import re
from datetime import date
from decimal import Decimal

from cre_brain.domain import ClaimType, Fact
from cre_brain.extraction.preparse.models import ParsedCell, ParsedText, digest
from cre_brain.extraction.schemas import OUTPUTS, Observation, SourceDocument
from cre_brain.gates.limits import bounded_decimal
from cre_brain.gates.numbers import extract_numbers
from cre_brain.runner.tools.contracts import AuthenticatedContext
from cre_brain.runner.tools.json_io import canonical, parse

TEXT_FIELDS = frozenset({"unit_id", "property_name", "period"})
DATE_FIELDS = frozenset({"lease_end", "as_of"})
UNITS = {
    "rent": "USD/month",
    "rent_total": "USD/month",
    "income": "USD",
    "income_total": "USD",
    "expense": "USD",
    "expense_total": "USD",
    "units": "count",
    "units_total": "count",
    "asking_price": "USD",
}


def anchors(source: SourceDocument) -> dict[str, ParsedCell | ParsedText]:
    return {
        **{c.cell_id: c for t in source.document.tables for c in t.cells},
        **{t.text_id: t for t in source.document.texts},
    }


def observed_value(anchor: ParsedCell | ParsedText, field: str) -> tuple[str | Decimal | date, str]:
    raw = anchor.text
    if isinstance(anchor, ParsedCell) and anchor.kind not in {"text", "number", "date"}:
        raise ValueError("Formula/cache/boolean/error/empty observations cannot authorize fields")
    if field in TEXT_FIELDS:
        if isinstance(anchor, ParsedCell) and anchor.kind != "text":
            raise ValueError("Text fields require text observations")
        return raw, "text"
    if field in DATE_FIELDS:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            raise ValueError("Only exact unambiguous ISO date source observations are supported")
        return date.fromisoformat(raw), "date"
    if isinstance(anchor, ParsedCell) and anchor.kind == "date":
        raise ValueError("Date observation cannot authorize numeric fields")
    if any(c.isdigit() and c not in "0123456789" for c in raw):
        raise ValueError("Unsupported non-ASCII numeric observation")
    unit = UNITS[field]
    if isinstance(anchor, ParsedCell) and anchor.kind == "number":
        if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw):
            raise ValueError("Unsupported native numeric lexeme")
        # Bound lexeme/exponent before Decimal construction; existing finance bounds apply.
        if len(raw) > 128 or ("e" in raw.lower() and abs(int(raw.lower().split("e")[1])) > 32):
            raise ValueError("Native numeric lexeme exceeds finance bounds")
        value = bounded_decimal(Decimal(raw))
    else:
        text = raw.strip()
        if "(" in text or ")" in text:
            if (
                not text.startswith("(")
                or not text.endswith(")")
                or text.count("(") != 1
                or text.count(")") != 1
                or any(sign in text[1:-1] for sign in ("+", "-", "−"))
            ):
                raise ValueError("Require balanced, unsigned accounting source observation")
        tokens = extract_numbers(text)
        if len(tokens) != 1 or tokens[0].start != 0 or tokens[0].end != len(text):
            raise ValueError("Require one complete deterministic numeric source observation")
        token = tokens[0]
        if token.date_value is not None or token.unit not in {"number", unit, unit.split("/")[0]}:
            raise ValueError("Source number has incompatible units")
        value = bounded_decimal(token.value)
    if unit == "count" and (value < 0 or value != value.to_integral_value()):
        raise ValueError("Count observations require nonnegative integral source values")
    return value, unit


def convert(source: SourceDocument, raw: str, context: AuthenticatedContext) -> tuple[Fact, ...]:
    body = parse(raw)
    schema = OUTPUTS[source.doc_type]
    output = schema.model_validate_json(canonical(body))
    required = {(s.field, s.anchor_id, s.anchor_kind) for s in source.required}
    observations: dict[str, Observation] = {}
    item: Observation
    for item in output.observations:
        if (
            item.anchor_id in observations
            or (item.field, item.anchor_id, item.anchor_kind) not in required
        ):
            raise ValueError("Duplicate, wrong-field/kind or unregistered source anchor")
        observations[item.anchor_id] = item
    if len(observations) != len(required):
        raise ValueError("Missing host-required source observations")
    index = anchors(source)
    facts = []
    keys = set()
    for selection in source.required:
        item = observations[selection.anchor_id]
        anchor = index[selection.anchor_id]
        if (
            item.quote != anchor.text
            or item.value != anchor.text
            or anchor.anchor.doc_id != source.document.doc_id
            or (item.anchor_kind == "cell") != isinstance(anchor, ParsedCell)
        ):
            raise ValueError("Quote/value/kind/document differs from exact source anchor")
        value, unit = observed_value(anchor, item.field)
        # Same semantic field twice in one source row (or page-text singleton) collides.
        location = (
            (anchor.anchor.sheet, re.sub(r"^[A-Z]+", "", anchor.anchor.cell))
            if isinstance(anchor, ParsedCell)
            else (anchor.anchor.page, anchor.anchor.bbox)
        )
        key = f"{source.document.doc_id}.{item.field}.{digest(location)[:16]}"
        if key in keys:
            raise ValueError("Semantic field collision")
        keys.add(key)
        facts.append(
            Fact(
                fact_id="ex-"
                + digest(
                    (
                        context.scope.model_dump(),
                        context.deal_id,
                        source.parsed_sha256,
                        item.field,
                        item.anchor_id,
                    )
                ),
                deal_id=context.deal_id,
                key=key,
                value=value,
                unit=unit,
                claim_type=ClaimType.SELLER_ASSERTION,
                provenance=[anchor.provenance.model_copy(deep=True)],
                known_at=context.started_at,
                version=1,
            )
        )
    return tuple(facts)
