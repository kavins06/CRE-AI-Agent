"""Typed gate requirements supplied by trusted tool/firm-policy composition.

Requirements are not analyst-issued verdicts. Citations are untrusted identity
claims: the checker reloads canonical state and checks every displayed occurrence.
TrustedInputs is a local composition seam, never a runner tool. A durable host
can implement InputProvider with the same tenant/deal/version semantics.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

from pydantic import ConfigDict, Field, model_validator

from cre_brain.domain import Deliverable, GateResult
from cre_brain.domain.base import Identifier, TenantScope
from cre_brain.domain.models import DomainModel
from cre_brain.excel.models import TemplateMap
from cre_brain.finance.proforma import ProFormaInput
from cre_brain.finance.returns import ReturnsInput
from cre_brain.finance.scenarios import FragilityInput
from cre_brain.rules.models import AssumptionPolicy, BuyBoxPolicy, LoiPolicy


class Boundary(DomainModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always"
    )


class EvidenceRef(Boundary):
    kind: Literal["fact", "calc"]
    record_id: Identifier
    deal_id: Identifier
    version: int = Field(default=1, strict=True, ge=1)
    key: Identifier
    unit: str
    function: str | None = None
    period: str | None = None

    @model_validator(mode="after")
    def coherent(self) -> "EvidenceRef":
        if (self.kind == "calc") != (self.function is not None):
            raise ValueError("Only calculation references require a function identity")
        return self


class NumberCitation(Boundary):
    start: int = Field(strict=True, ge=0)
    end: int = Field(strict=True, gt=0)
    reference: EvidenceRef

    @model_validator(mode="after")
    def ordered(self) -> "NumberCitation":
        if self.end <= self.start:
            raise ValueError("Citation needs a nonempty exact text span")
        return self


class CoverageField(Boundary):
    name: Identifier
    doc_id: Identifier
    references: tuple[EvidenceRef, ...] = Field(min_length=1)


class Checksum(Boundary):
    name: Identifier
    parts: tuple[EvidenceRef, ...] = Field(min_length=1)
    total: EvidenceRef
    unit: str


class AssumptionCheck(Boundary):
    record_id: Identifier
    deal_id: Identifier
    unit: str
    version: int = Field(default=1, strict=True, ge=1)


class RuleCheck(Boundary):
    references: dict[str, EvidenceRef]


class ReturnCheck(Boundary):
    reference: EvidenceRef
    input_id: Identifier


class ScenarioCheck(Boundary):
    input_id: Identifier
    result: EvidenceRef
    assumptions: dict[str, EvidenceRef]


class FragilityCheck(Boundary):
    input_id: Identifier
    deal_id: Identifier
    base: EvidenceRef
    scenarios: tuple[ScenarioCheck, ...] = Field(min_length=1)


class WorkbookCheck(Boundary):
    template: Path
    mapping: TemplateMap
    deal_id: Identifier
    calculations: dict[str, Identifier]


class FinanceRecipe(Boundary):
    """Host-issued immutable recipe, never a callback or a supplied result.

    Only these finance functions can authorize numbers. More functions require
    explicit typed implementations here; missing recipes refuse finalization.
    Dependencies pin numeric input fields to canonical Fact/Calc identities.
    A source with no dependencies is an immutable host-issued numeric input.
    """

    calc_id: Identifier
    function: Literal["calculate_returns", "build_proforma"]
    code_version: Identifier
    source: ReturnsInput | ProFormaInput
    dependencies: dict[str, EvidenceRef] = Field(default_factory=dict)
    model_id: Identifier | None = None
    model_version: int = Field(default=1, strict=True, ge=1)
    scenario_parameters: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def compatible(self) -> "FinanceRecipe":
        if (self.function == "calculate_returns") != isinstance(self.source, ReturnsInput):
            raise ValueError("Recipe function must match its typed finance input")
        return self


class ModelContract(Boundary):
    """Host inventory of the actual model artifact, recipe and assumptions."""

    calc_id: Identifier
    deal_id: Identifier
    code_version: Identifier
    model_id: Identifier
    model_version: int = Field(strict=True, ge=1)
    artifact: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assumptions: dict[str, AssumptionCheck] = Field(default_factory=dict)


class GatePlan(Boundary):
    model: ModelContract | None = None
    coverage: tuple[CoverageField, ...] = ()
    checksums: tuple[Checksum, ...] = ()
    citations: tuple[NumberCitation, ...] = ()
    model_bindings: dict[str, EvidenceRef] = Field(default_factory=dict)
    required_sections: tuple[str, ...] = ()
    workbook: WorkbookCheck | None = None
    buy_box: RuleCheck | None = None
    assumption_ranges: RuleCheck | None = None
    policy_bands: RuleCheck | None = None
    returns: tuple[ReturnCheck, ...] = ()
    assumptions: tuple[AssumptionCheck, ...] = ()
    fragility: FragilityCheck | None = None
    buy_box_policy: BuyBoxPolicy = Field(default_factory=BuyBoxPolicy)
    assumption_policy: AssumptionPolicy = Field(default_factory=AssumptionPolicy)
    loi_policy: LoiPolicy = Field(default_factory=LoiPolicy)
    # Trusted firm vocabulary, keyed by canonical fact/output key (not values).
    labels: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    extraction: bool = False


FinanceInput = ReturnsInput | FragilityInput | ProFormaInput


class InputProvider(Protocol):
    def identity(self, scope: TenantScope, deliverable: Deliverable) -> Deliverable | None: ...
    def recipe(self, scope: TenantScope, deal_id: str, calc_id: str) -> FinanceRecipe | None: ...
    def plan(self, scope: TenantScope, deliverable: Deliverable) -> GatePlan | None: ...
    def finance_input(
        self, scope: TenantScope, deal_id: str, input_id: str
    ) -> FinanceInput | None: ...
    def input_deals(self, scope: TenantScope, input_id: str) -> tuple[str, ...]: ...


class TrustedInputs:
    """Server-owned immutable finance inputs and versioned requirement snapshots.

    Never expose put_input/put_plan to the analyst. Policies, units for calculation
    outputs (absent from CalcResult), coverage inventories and section names must
    come from trusted tools/onboarding. No PASS object or workbook descriptor is
    accepted here. Plans may be revised for the same draft version.
    """

    def __init__(self) -> None:
        self._plans: dict[tuple[str, str, str, int], tuple[Deliverable, GatePlan]] = {}
        self._recipes: dict[tuple[str, str, str, str], FinanceRecipe] = {}
        self._inputs: dict[tuple[str, str, str, str], FinanceInput] = {}

    def put_plan(self, scope: TenantScope, deliverable: Deliverable, plan: GatePlan) -> None:
        key = (scope.user_id, scope.firm_id, deliverable.d_id, deliverable.version)
        canonical = Deliverable.model_validate(
            deliverable.model_dump(exclude={"gate_results"}) | {"gate_results": []}
        )
        if key in self._plans and self._plans[key][0] != canonical:
            raise ValueError("Canonical deliverable metadata is immutable per version")
        self._plans[key] = (canonical, GatePlan.model_validate(plan.model_dump()))

    def plan(self, scope: TenantScope, deliverable: Deliverable) -> GatePlan | None:
        entry = self._plans.get(
            (scope.user_id, scope.firm_id, deliverable.d_id, deliverable.version)
        )
        if entry is None or self.identity(scope, deliverable) is None:
            return None
        return GatePlan.model_validate(entry[1].model_dump())

    def identity(self, scope: TenantScope, deliverable: Deliverable) -> Deliverable | None:
        entry = self._plans.get(
            (scope.user_id, scope.firm_id, deliverable.d_id, deliverable.version)
        )
        if entry is None:
            return None
        supplied = deliverable.model_dump(exclude={"gate_results"})
        if entry[0].model_dump(exclude={"gate_results"}) != supplied:
            return None
        return Deliverable.model_validate(entry[0].model_dump())

    def put_recipe(self, scope: TenantScope, deal_id: str, recipe: FinanceRecipe) -> None:
        from cre_brain.gates.limits import bounded_values

        bounded_values(recipe)
        recipe = FinanceRecipe.model_validate(recipe.model_dump())
        key = (scope.user_id, scope.firm_id, deal_id, recipe.calc_id)
        if key in self._recipes and self._recipes[key] != recipe:
            raise ValueError("Canonical finance recipes are immutable")
        if not recipe.dependencies:
            self.put_input(scope, deal_id, recipe.source)
        self._recipes[key] = recipe

    def recipe(self, scope: TenantScope, deal_id: str, calc_id: str) -> FinanceRecipe | None:
        recipe = self._recipes.get((scope.user_id, scope.firm_id, deal_id, calc_id))
        return None if recipe is None else FinanceRecipe.model_validate(recipe.model_dump())

    def put_input(self, scope: TenantScope, deal_id: str, item: FinanceInput) -> None:
        from cre_brain.gates.limits import bounded_values

        bounded_values(item)
        item = type(item).model_validate(item.model_dump())
        key = (scope.user_id, scope.firm_id, deal_id, item.input_id)
        if key in self._inputs and self._inputs[key] != item:
            raise ValueError("Canonical finance input identities are immutable")
        self._inputs[key] = item

    def finance_input(self, scope: TenantScope, deal_id: str, input_id: str) -> FinanceInput | None:
        item = self._inputs.get((scope.user_id, scope.firm_id, deal_id, input_id))
        return None if item is None else type(item).model_validate(item.model_dump())

    def input_deals(self, scope: TenantScope, input_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    key[2]
                    for key in self._inputs
                    if key[:2] == (scope.user_id, scope.firm_id) and key[3] == input_id
                }
            )
        )


class NumberToken(Boundary):
    start: int
    end: int
    raw: str
    value: Decimal
    unit: str
    display_unit: str
    date_value: date | None = None


class GateRegistration(Boundary):
    name: str
    blocking: bool


class GateReport(Boundary):
    results: dict[str, "GateResult"]
    blocking_failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.blocking_failures


GateReport.model_rebuild()
