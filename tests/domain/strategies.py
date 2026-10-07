"""Reusable Hypothesis strategies for persisted domain records."""

from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import strategies as st

from cre_brain.domain import (
    AgentEvent,
    CalcResult,
    ClaimType,
    Fact,
    Provenance,
)

identifiers = st.from_regex(r"[a-z][a-z0-9_-]{0,15}", fullmatch=True)
decimals = st.decimals(
    min_value=Decimal("-1000000000"),
    max_value=Decimal("1000000000"),
    allow_nan=False,
    allow_infinity=False,
    places=4,
)
provenances = st.builds(
    Provenance,
    doc_id=identifiers,
    page=st.one_of(st.none(), st.integers(min_value=1, max_value=10_000)),
    quote=st.one_of(st.none(), st.text(max_size=100)),
)
facts = st.builds(
    Fact,
    fact_id=identifiers,
    deal_id=identifiers,
    key=identifiers,
    value=st.one_of(
        decimals,
        st.text(max_size=40),
        st.dates(min_value=date(1900, 1, 1), max_value=date(2200, 1, 1)),
        st.booleans(),
    ),
    unit=st.one_of(st.none(), identifiers),
    claim_type=st.sampled_from(list(ClaimType)),
    provenance=st.lists(provenances, max_size=3),
    known_at=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2100, 1, 1),
        timezones=st.just(UTC),
    ),
    version=st.integers(min_value=1, max_value=1000),
)
calc_results = st.builds(
    CalcResult,
    calc_id=identifiers,
    fn=identifiers,
    inputs=st.dictionaries(identifiers, identifiers, max_size=5),
    outputs=st.dictionaries(identifiers, decimals, max_size=5),
    code_version=identifiers,
)
agent_events = st.builds(
    AgentEvent,
    event_id=identifiers,
    task_id=identifiers,
    seq=st.one_of(st.none(), st.integers(min_value=1, max_value=1000)),
    origin=st.one_of(
        st.none(),
        st.tuples(
            identifiers,
            st.integers(min_value=0, max_value=100),
            st.integers(min_value=0, max_value=1000),
        ),
    ),
    ts=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2100, 1, 1),
        timezones=st.just(UTC),
    ),
    source=st.sampled_from(AgentEvent.SOURCES),
    kind=st.sampled_from(AgentEvent.KINDS),
    cause_id=st.one_of(st.none(), identifiers),
    release_id=identifiers,
    runner=identifiers,
    payload=st.dictionaries(identifiers, st.integers(), max_size=5),
)

__all__ = ["agent_events", "calc_results", "facts", "provenances"]
