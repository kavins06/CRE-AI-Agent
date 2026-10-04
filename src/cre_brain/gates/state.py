"""Reload and validate canonical identities, lineage, freshness and deal scope."""

from datetime import UTC, date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import Engine, select

from cre_brain.domain import CalcResult, ClaimType, Deliverable, Fact
from cre_brain.domain.base import TenantScope
from cre_brain.gates.authority import input_unit, numeric_inputs, output_unit, reproduce
from cre_brain.gates.limits import GateFailure, bounded_payload, bounded_values
from cre_brain.gates.models import EvidenceRef, FinanceRecipe, InputProvider
from cre_brain.state.graph import DependencyGraph
from cre_brain.state.store import SqlVersionedStore, tenant_filter

UNITS = frozenset(
    {
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CAD",
        "AUD",
        "CHF",
        "USD/month",
        "USD/year",
        "USD/unit",
        "USD/sqft",
        "ratio",
        "count",
        "number",
        "days",
        "year",
        "sqft",
        "date",
        "text",
        "bool",
    }
)


class GateStore[RecordT: BaseModel](SqlVersionedStore[RecordT]):
    """Domain store reader with a numeric serialization budget before decoding."""

    def get(
        self, record_id: str, *, scope: TenantScope, version: int | None = None
    ) -> RecordT | None:
        query = select(self.table.c.payload).where(
            tenant_filter(self.table, scope),
            self.table.c.record_id == record_id,
        )
        if version is not None:
            query = query.where(self.table.c.version == version)
        query = query.order_by(self.table.c.version.desc()).limit(1)
        with self.engine.connect() as connection:
            payload = connection.execute(query).scalar_one_or_none()
        if payload is None:
            return None
        bounded_payload(payload)
        record = self.model.model_validate(payload)
        bounded_values(record)
        return record


class CanonicalState:
    def __init__(
        self, engine: Engine, scope: TenantScope, inputs: InputProvider, as_of: date
    ) -> None:
        self.engine, self.scope, self.inputs, self.as_of = engine, scope, inputs, as_of
        self.facts = GateStore(engine, Fact)
        self.calcs = GateStore(engine, CalcResult)

    def fresh(self, identity: str) -> None:
        if identity in DependencyGraph(self.engine, release_id="gates").tenant_stale_items(
            scope=self.scope
        ):
            raise ValueError(f"Stale canonical dependency {identity}")

    def fact(self, identity: str, deal_id: str) -> Fact:
        self.fresh(identity)
        fact = self.facts.get(identity, scope=self.scope)
        if fact is None or self.calcs.get(identity, scope=self.scope) is not None:
            raise ValueError(f"Missing or ambiguous canonical fact {identity}")
        if fact.fact_id != identity:
            raise GateFailure("canonical_mismatch")
        bounded_values(fact)
        fact = Fact.model_validate(fact.model_dump())
        if fact.deal_id != deal_id or fact.claim_type == ClaimType.CONFLICT:
            raise ValueError("Fact has incompatible deal scope or unresolved conflict")
        if fact.known_at.utcoffset() is None or fact.known_at.astimezone(UTC).date() > self.as_of:
            raise ValueError("Fact is outside the as-of knowledge boundary")
        if fact.valid_time and (
            (fact.valid_time.start is not None and fact.valid_time.start > self.as_of)
            or (fact.valid_time.end is not None and fact.valid_time.end < self.as_of)
        ):
            raise ValueError("Fact is outside its valid time")
        if not fact.provenance:
            raise ValueError("Fact requires canonical source provenance")
        # Two fact identities for a semantic key cannot be selected by convenience.
        with self.engine.connect() as connection:
            identities = (
                connection.execute(
                    select(self.facts.table.c.record_id)
                    .where(tenant_filter(self.facts.table, self.scope))
                    .distinct()
                )
                .scalars()
                .all()
            )
        matches = [
            f
            for i in identities
            if (f := self.facts.get(i, scope=self.scope)) is not None
            and f.deal_id == deal_id
            and f.key == fact.key
        ]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous canonical fact key {fact.key}")
        return fact

    def fact_for_key(self, key: str, deal_id: str) -> Fact:
        with self.engine.connect() as connection:
            identities = (
                connection.execute(
                    select(self.facts.table.c.record_id)
                    .where(tenant_filter(self.facts.table, self.scope))
                    .distinct()
                )
                .scalars()
                .all()
            )
        matches = [
            fact
            for identity in identities
            if (fact := self.facts.get(identity, scope=self.scope)) is not None
            and fact.key == key
            and fact.deal_id == deal_id
        ]
        if len(matches) != 1:
            raise GateFailure("canonical_mismatch")
        return self.fact(matches[0].fact_id, deal_id)

    def calc(self, identity: str, deal_id: str, active: frozenset[str] = frozenset()) -> CalcResult:
        self.fresh(identity)
        if identity in active:
            raise ValueError("Circular canonical calculation dependencies")
        calc = self.calcs.get(identity, scope=self.scope)
        if calc is None or self.facts.get(identity, scope=self.scope) is not None:
            raise ValueError(f"Missing or ambiguous canonical calculation {identity}")
        bounded_values(calc)
        calc = CalcResult.model_validate(calc.model_dump())
        with self.engine.connect() as connection:
            payloads = (
                connection.execute(
                    select(self.calcs.table.c.payload).where(
                        tenant_filter(self.calcs.table, self.scope),
                        self.calcs.table.c.record_id == identity,
                    )
                )
                .scalars()
                .all()
            )
        for payload in payloads:
            bounded_payload(payload)
        if any(CalcResult.model_validate(p) != calc for p in payloads):
            raise ValueError("Divergent versions of a canonical calculation identity")
        if not calc.inputs or not calc.outputs or not calc.code_version.strip():
            raise ValueError("Calculation requires canonical input/output/code identities")
        for dependency in calc.inputs.values():
            self.fresh(dependency)
            fact = self.facts.get(dependency, scope=self.scope)
            child = self.calcs.get(dependency, scope=self.scope)
            deals = self.inputs.input_deals(self.scope, dependency)
            if sum((fact is not None, child is not None, bool(deals))) != 1:
                raise ValueError(f"Missing or ambiguous scoped dependency {dependency}")
            if fact is not None:
                self.fact(dependency, deal_id)
            elif child is not None:
                self.calc(dependency, deal_id, active | {identity})
            elif deals != (deal_id,):
                raise ValueError("Finance input has ambiguous or incompatible deal scope")
        recipe = self.inputs.recipe(self.scope, deal_id, identity)
        if recipe is None:
            raise GateFailure("authority_unavailable")
        bounded_values(recipe)
        recipe = FinanceRecipe.model_validate(recipe.model_dump())
        if (
            recipe.calc_id != identity
            or recipe.code_version != calc.code_version
            or recipe.function != calc.fn
        ):
            raise GateFailure("canonical_mismatch")
        values = numeric_inputs(recipe)
        for key, ref in recipe.dependencies.items():
            if ref.deal_id != deal_id or key not in values or ref.unit != input_unit(recipe, key):
                raise GateFailure("canonical_mismatch")
            if ref.kind == "fact":
                fact = self.fact(ref.record_id, deal_id)
                if (
                    fact.version != ref.version
                    or fact.key != ref.key
                    or fact.unit != ref.unit
                    or fact.value != values[key]
                ):
                    raise GateFailure("canonical_mismatch")
            else:
                child = self.calc(ref.record_id, deal_id, active | {identity})
                if (
                    ref.version != 1
                    or child.fn != ref.function
                    or ref.unit != output_unit(child.fn, ref.key)
                    or child.outputs.get(ref.key) != values[key]
                ):
                    raise GateFailure("canonical_mismatch")
        if calc != reproduce(recipe):
            raise GateFailure("canonical_mismatch")
        return calc

    def resolve(self, ref: EvidenceRef, deliverable: Deliverable) -> Decimal | str | date | bool:
        ref = EvidenceRef.model_validate(ref.model_dump())
        if ref.deal_id not in deliverable.deal_ids or ref.unit not in UNITS:
            raise ValueError("Unsupported evidence unit or incompatible deal")
        if ref.kind == "fact":
            fact = self.fact(ref.record_id, ref.deal_id)
            if fact.version != ref.version or fact.key != ref.key or fact.unit != ref.unit:
                raise ValueError("Fact identity/version/key/unit does not match canonical state")
            return fact.value
        if ref.version != 1:
            raise ValueError(
                "Calculation references use immutable identity, not arbitrary versions"
            )
        calc = self.calc(ref.record_id, ref.deal_id)
        if (
            calc.fn != ref.function
            or ref.key not in calc.outputs
            or ref.unit != output_unit(calc.fn, ref.key)
        ):
            raise ValueError("Calculation function/output identity mismatch")
        return calc.outputs[ref.key]
