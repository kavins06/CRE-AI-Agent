from decimal import Decimal, localcontext

import pytest

from cre_brain.gates import extract_numbers


@pytest.mark.parametrize(
    ("text", "values", "units"),
    [
        (
            "price -$1,250.50; loss ($2.5 million); yield −5.25%",
            ["-1250.50", "-2500000", "-0.0525"],
            ["USD", "USD", "ratio"],
        ),
        (
            "price USD 1.2m–1.5m; units 50–60; ratio .75",
            ["1200000", "1500000", "50", "60", ".75"],
            ["USD", "USD", "number", "number", "number"],
        ),
        (
            "| price | growth |\n| €1 250,000 | 2–3% |",
            ["1250000", ".02", ".03"],
            ["EUR", "ratio", "ratio"],
        ),
        (
            "> 999\n`123` [price 456](https://example/789) **12** <span>34</span> [^56]",
            ["999", "123", "456", "789", "12", "34", "56"],
            ["number"] * 7,
        ),
        (
            "price £4bn; CHF 3.0; CAD 2,000; 1e3",
            ["4000000000", "3.0", "2000", "1000"],
            ["GBP", "CHF", "CAD", "number"],
        ),
    ],
)
def test_t037_ac2_extract_display_units_signs_ranges_and_formatting(text, values, units):
    with localcontext() as context:
        context.prec = 2
        numbers = extract_numbers(text)
    assert [n.value for n in numbers] == [Decimal(v) for v in values]
    assert [n.unit for n in numbers] == units
    assert all(text[n.start : n.end] == n.raw for n in numbers)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "$1,23", "10 bitcoins", "0xFF", "1/2"])
def test_t037_ac2_unsupported_numeric_syntax_fails_closed(text):
    with pytest.raises(ValueError):
        extract_numbers(text)


@pytest.mark.parametrize(
    ("text", "values", "units"),
    [
        ("price $1–2 million", ["1000000", "2000000"], ["USD", "USD"]),
        ("growth 2 - 3%", [".02", ".03"], ["ratio", "ratio"]),
        (
            "rent $100/month; area 1,000 sqft; period 30 days",
            ["100", "1000", "30"],
            ["USD/month", "sqft", "days"],
        ),
        ("yield 25 BPS", [".0025"], ["ratio"]),
        ("price $1.5 - $2m", ["1500000", "2000000"], ["USD", "USD"]),
    ],
)
def test_t037_ac2_range_suffixes_and_dimensions(text, values, units):
    tokens = extract_numbers(text)
    assert [t.value for t in tokens] == [Decimal(v) for v in values]
    assert [t.unit for t in tokens] == units


@pytest.mark.parametrize(
    "text",
    [
        "price 100 bananas",
        "price 10 XYZ",
        "price $100/fortnight",
        "100..2",
        "price 1,000,00",
        "price $1e999999",
        "price 5%%",
    ],
)
def test_t037_ac2_unsupported_units_and_ambiguous_values(text):
    with pytest.raises(ValueError):
        extract_numbers(text)


@pytest.mark.parametrize(
    "text",
    [
        "price &minus;100",
        "price &#49;&#50;",
        "price 1**2**",
        "price €**100**",
        "loss (**100**)",
        "growth **5**%",
    ],
)
def test_t037_ac2_encoded_or_split_numeric_displays_fail_closed(text):
    with pytest.raises(ValueError):
        extract_numbers(text)


def test_t037_ac2_date_is_one_canonical_display_identity():
    from datetime import date

    tokens = extract_numbers("as of 2026-10-04")
    assert len(tokens) == 1
    assert tokens[0].date_value == date(2026, 10, 4)
    assert tokens[0].unit == "date"


def test_t037_ac2_table_column_display_units_are_preserved():
    text = "| Price ($m) | Yield (%) |\n|---|---|\n| 1.2–1.5 | 5–6 |"
    tokens = extract_numbers(text)
    assert [n.value for n in tokens] == [
        Decimal("1200000"),
        Decimal("1500000"),
        Decimal(".05"),
        Decimal(".06"),
    ]
    assert [n.unit for n in tokens] == ["USD", "USD", "ratio", "ratio"]
    assert all(text[n.start : n.end] == n.raw for n in tokens)
