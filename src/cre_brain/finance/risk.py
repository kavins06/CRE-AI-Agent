"""Uncalibrated SCREEN threshold-breach index, configured by immutable host policy."""

from fractions import Fraction

from pydantic import Field, model_validator

from cre_brain.domain import CalcResult
from cre_brain.finance._arithmetic import decimal_value
from cre_brain.finance._context import _calculation
from cre_brain.rules.models import Boundary, Identifier, Policy, Ratio


class RiskPolicy(Policy):
    # No numeric defaults: thresholds and weights must be explicitly issued by the host.
    min_occupancy: Ratio = Field(ge=0, le=1)
    min_dscr: Ratio = Field(gt=0, le=100)
    occupancy_weight: Ratio = Field(ge=0, le=1)
    dscr_weight: Ratio = Field(ge=0, le=1)

    @model_validator(mode="after")
    def supported(self) -> "RiskPolicy":
        if not self.source_ids or Fraction(self.occupancy_weight) + Fraction(self.dscr_weight) != 1:
            raise ValueError("Risk policy needs provenance and weights summing exactly to one")
        return self


class RiskInput(Boundary):
    input_id: Identifier
    occupancy: Ratio = Field(ge=0, le=1)
    dscr: Ratio = Field(ge=0, le=100)
    policy: RiskPolicy


@_calculation
def risk_score(source: RiskInput, *, calc_id: str, code_version: str) -> CalcResult:
    source = RiskInput.model_validate(source.model_dump())
    score = Fraction(source.policy.occupancy_weight) * (
        source.occupancy < source.policy.min_occupancy
    ) + Fraction(source.policy.dscr_weight) * (source.dscr < source.policy.min_dscr)
    return CalcResult(
        calc_id=calc_id,
        fn="risk_score",
        inputs={"policy": source.input_id},
        outputs={"risk_score": decimal_value(score)},
        code_version=code_version,
    )
