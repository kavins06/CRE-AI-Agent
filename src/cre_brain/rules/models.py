"""Classification boundaries; these are not stored facts or finance CalcResults."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")]
Tier = Literal["A", "B", "C", "unknown"]
DataField = Literal["rent_roll", "t12", "price", "market_rent", "capex", "debt_terms"]
MAX_EXACT_INTEGER = 2**53 - 1


def scaled(value: Decimal, places: int) -> int:
    """Encode exactly without Decimal context rounding or binary floating point."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("A finite Decimal is required")
    sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int) or len(digits) > 32:
        raise ValueError("Unsupported Decimal precision")
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    shift = exponent + places
    if coefficient == 0:
        return 0
    integer: int
    if shift >= 0:
        if shift > 16:
            raise ValueError("Decimal exceeds exact integer range")
        integer = coefficient * 10**shift
    else:
        if -shift > 32:
            raise ValueError("Unsupported Decimal precision")
        integer, remainder = divmod(coefficient, 10**-shift)
        if remainder:
            raise ValueError(f"Decimal must be exact at {places} decimal places")
    if integer > MAX_EXACT_INTEGER:
        raise ValueError("Decimal exceeds exact integer range")
    return -integer if sign else integer


def _amount(value: Decimal) -> Decimal:
    scaled(value, 2)
    return value


def _ratio(value: Decimal) -> Decimal:
    scaled(value, 6)
    return value


Amount = Annotated[Decimal, Field(ge=0), AfterValidator(_amount)]
Ratio = Annotated[Decimal, AfterValidator(_ratio)]
Count = Annotated[int, Field(ge=0, le=1000000)]
Vintage = Annotated[int, Field(ge=1800, le=2100)]


class Boundary(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        revalidate_instances="always",
    )


class Policy(Boundary):
    policy_id: Identifier
    version: Identifier = "1.0.0"
    source_ids: tuple[Identifier, ...] = ()


class BuyBoxPolicy(Policy):
    """Illustrative firm screening defaults, not assertions of market truth."""

    policy_id: Identifier = "illustrative-buy-box"
    min_units: Count = 50
    max_units: Count = 500
    min_dscr: Annotated[Ratio, Field(ge=0)] = Decimal("1.25")
    max_price: Amount = Decimal("100000000")
    allowed_market_tiers: tuple[Literal["A", "B", "C"], ...] = ("A", "B")

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.min_units > self.max_units:
            raise ValueError("min_units must not exceed max_units")
        return self


class AssumptionProfile(Boundary):
    profile_id: Identifier
    market_tier: Literal["A", "B", "C"]
    asset_class: Literal["A", "B", "C"]
    min_vintage: Vintage = 1800
    max_vintage: Vintage = 2100
    min_rent_growth: Ratio = Decimal("-0.01")
    max_rent_growth: Ratio = Decimal("0.06")
    min_cap_rate: Annotated[Ratio, Field(ge=0)] = Decimal("0.035")
    max_cap_rate: Annotated[Ratio, Field(ge=0)] = Decimal("0.09")

    @model_validator(mode="after")
    def ordered(self) -> Self:
        for low, high in (
            (self.min_vintage, self.max_vintage),
            (self.min_rent_growth, self.max_rent_growth),
            (self.min_cap_rate, self.max_cap_rate),
        ):
            if low > high:
                raise ValueError("Profile lower bounds must not exceed upper bounds")
        return self


DEFAULT_PROFILES = (
    AssumptionProfile(
        profile_id="illustrative-A-new", market_tier="A", asset_class="A", min_vintage=2000
    ),
    AssumptionProfile(
        profile_id="illustrative-B-modern", market_tier="B", asset_class="B", min_vintage=1980
    ),
    AssumptionProfile(
        profile_id="illustrative-C",
        market_tier="C",
        asset_class="C",
        min_cap_rate=Decimal("0.05"),
        max_cap_rate=Decimal("0.12"),
    ),
)


class AssumptionPolicy(Policy):
    policy_id: Identifier = "illustrative-assumption-ranges"
    profiles: tuple[AssumptionProfile, ...] = DEFAULT_PROFILES

    @model_validator(mode="after")
    def unambiguous(self) -> Self:
        if len({p.profile_id for p in self.profiles}) != len(self.profiles):
            raise ValueError("Profile IDs must be unique")
        for index, a in enumerate(self.profiles):
            for b in self.profiles[index + 1 :]:
                if (
                    a.market_tier == b.market_tier
                    and a.asset_class == b.asset_class
                    and max(a.min_vintage, b.min_vintage) <= min(a.max_vintage, b.max_vintage)
                ):
                    raise ValueError("Assumption profiles must not overlap")
        return self


class LoiPolicy(Policy):
    policy_id: Identifier = "illustrative-loi"
    max_price: Amount = Decimal("100000000")
    min_dd_days: Count = 15
    max_dd_days: Count = 60
    min_close_days: Count = 30
    max_close_days: Count = 120
    max_deposit_percent: Annotated[Ratio, Field(ge=0, le=1)] = Decimal("0.03")
    require_financing_contingency: bool = True

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.min_dd_days > self.max_dd_days or self.min_close_days > self.max_close_days:
            raise ValueError("Policy lower bounds must not exceed upper bounds")
        return self


class MissingDataPolicy(Policy):
    policy_id: Identifier = "illustrative-missing-data"
    critical_fields: tuple[DataField, ...] = ("rent_roll", "t12", "price")
    allow_defaults: bool = True


class EscalationPolicy(Policy):
    policy_id: Identifier = "illustrative-escalation"
    require_external_approval: bool = True


class JurisdictionPolicy(Policy):
    jurisdiction: Identifier
    verified: bool = False


class RentPolicy(JurisdictionPolicy):
    policy_id: Identifier = "caller-rent-policy"
    status: Literal["regulated", "unregulated", "exempt", "unknown"] = "unknown"


class TaxPolicy(JurisdictionPolicy):
    policy_id: Identifier = "caller-tax-policy"
    status: Literal["on_transfer", "periodic", "none_on_transfer", "unknown"] = "unknown"


class RuleInput(Boundary):
    source_ids: tuple[Identifier, ...] = ()
    assumption_ids: tuple[Identifier, ...] = ()


class BuyBoxInput(RuleInput):
    units: Count | None = None
    dscr: Annotated[Ratio, Field(ge=0)] | None = None
    price: Amount | None = None
    market_tier: Tier = "unknown"
    policy: BuyBoxPolicy = Field(default_factory=BuyBoxPolicy)


class AssumptionInput(RuleInput):
    market_tier: Tier = "unknown"
    asset_class: Tier = "unknown"
    vintage: Vintage | None = None
    rent_growth: Ratio | None = None
    cap_rate: Annotated[Ratio, Field(ge=0)] | None = None
    policy: AssumptionPolicy = Field(default_factory=AssumptionPolicy)


class LoiInput(RuleInput):
    price: Amount | None = None
    dd_days: Count | None = None
    close_days: Count | None = None
    deposit_percent: Annotated[Ratio, Field(ge=0, le=1)] | None = None
    financing_contingency: bool | None = None
    policy: LoiPolicy = Field(default_factory=LoiPolicy)


class MissingDataInput(RuleInput):
    missing_fields: tuple[DataField, ...] = ()
    policy: MissingDataPolicy = Field(default_factory=MissingDataPolicy)


class EscalationInput(RuleInput):
    evidence_conflict: bool = False
    legal_uncertainty: bool = False
    policy_exception: bool = False
    external_action: bool = False
    material_uncertainty: bool = False
    policy: EscalationPolicy = Field(default_factory=EscalationPolicy)


class RentInput(RuleInput):
    jurisdiction: Identifier
    policy: RentPolicy | None = None


class TaxInput(RuleInput):
    jurisdiction: Identifier
    policy: TaxPolicy | None = None


Classification = Literal[
    "eligible",
    "ineligible",
    "review_required",
    "within_policy",
    "outside_policy",
    "approval_required",
    "complete",
    "blocked",
    "proceed_with_assumptions",
    "clarification_required",
    "continue",
    "stop",
    "legal_review",
    "regulated",
    "unregulated",
    "exempt",
    "reassessment_required",
    "periodic_review",
    "no_transfer_reassessment",
]


class Decision(Boundary):
    classification: Classification
    reason_code: Identifier
    required_checks: tuple[Identifier, ...]


class TraceNode(Boundary):
    node_id: Identifier
    name: Identifier
    order: Count
    input_json: str
    output_json: str
    trace_data_json: str


class RuleMatch(Boundary):
    rule_id: Identifier
    index: Count


class EvaluationTrace(Boundary):
    table_id: Identifier
    table_version: Identifier
    table_sha256: str
    engine_version: Literal["2.1.2"]
    policy_id: Identifier
    policy_version: Identifier
    policy_sha256: str
    input_json: str
    input_sha256: str
    source_ids: tuple[Identifier, ...]
    assumption_ids: tuple[Identifier, ...]
    profile_id: Identifier | None = None
    nodes: tuple[TraceNode, ...]
    matched_rules: tuple[RuleMatch, ...]


class EvaluationResult(Boundary):
    decision: Decision
    trace: EvaluationTrace
