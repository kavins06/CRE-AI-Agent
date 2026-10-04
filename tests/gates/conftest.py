from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from cre_brain.config.settings import GateSettings
from cre_brain.domain import ClaimType, Deliverable, DeliverableKind, Fact, Provenance
from cre_brain.domain.base import TenantScope
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore


@pytest.fixture
def gate_env(tmp_path):
    from cre_brain.gates import GateService, TrustedInputs

    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    scope = TenantScope(user_id="user", firm_id="firm")
    gates = GateSettings(
        parity_abs="1",
        parity_rel="0.000001",
        checksum_abs="1",
        number_abs="1",
        number_rel="0.000001",
        fragility_margin="0.02",
        excel_functions=("SUM", "IF", "MAX"),
    )
    inputs = TrustedInputs()
    service = GateService(
        engine,
        scope=scope,
        settings=gates,
        inputs=inputs,
        scratch=tmp_path / "scratch",
        as_of=date(2026, 10, 4),
    )
    path = tmp_path / "memo.md"
    path.write_text("price $100\n", encoding="utf-8")
    deliverable = Deliverable(
        d_id="deliverable",
        deal_ids=["deal"],
        kind=DeliverableKind.IC_MEMO,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=["price"],
    )
    fact = Fact(
        fact_id="price",
        deal_id="deal",
        key="price",
        value=Decimal(100),
        unit="USD",
        claim_type=ClaimType.VERIFIED_FACT,
        provenance=[Provenance(doc_id="document", page=1)],
        known_at=datetime(2026, 10, 1, tzinfo=UTC),
        version=1,
    )
    SqlVersionedStore(engine, Fact).append(fact, scope=scope)
    yield service, inputs, engine, scope, deliverable, path, fact
    engine.dispose()
