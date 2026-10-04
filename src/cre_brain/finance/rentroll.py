"""Deterministic normalized rent-roll metrics."""

from decimal import Decimal
from urllib.parse import quote

from pydantic import Field, model_validator

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel

ZERO = Decimal()


class RentRollUnit(DomainModel):
    unit_id: Identifier
    input_id: Identifier
    unit_type: str = Field(min_length=1, max_length=64)
    market_rent: Decimal = Field(ge=0)
    contract_rent: Decimal = Field(ge=0)
    occupied: bool
    monthly_concession: Decimal = Field(default=ZERO, ge=0)

    @model_validator(mode="after")
    def possible(self) -> "RentRollUnit":
        if self.contract_rent > self.market_rent:
            raise ValueError("Contract rent above market requires separate gain-to-lease handling")
        if not self.occupied and (self.contract_rent or self.monthly_concession):
            raise ValueError("Vacant units cannot have contract rent or concessions")
        if self.monthly_concession > self.contract_rent:
            raise ValueError("Concessions cannot exceed contract rent")
        return self


def normalize_rent_roll(
    units: list[RentRollUnit], *, calc_id: str, code_version: str
) -> CalcResult:
    if not units:
        raise ValueError("Rent roll requires at least one unit")
    if len({unit.unit_id for unit in units}) != len(units):
        raise ValueError("Rent roll unit IDs must be unique")
    gpr = sum((unit.market_rent for unit in units), ZERO)
    if gpr <= 0:
        raise ValueError("Rent roll GPR must be positive")
    occupied = [unit for unit in units if unit.occupied]
    contract = sum((unit.contract_rent for unit in occupied), ZERO)
    concessions = sum((unit.monthly_concession for unit in occupied), ZERO)
    outputs = {
        "total_units": Decimal(len(units)),
        "occupied_units": Decimal(len(occupied)),
        "physical_occupancy": Decimal(len(occupied)) / Decimal(len(units)),
        "gpr_monthly": gpr,
        "loss_to_lease_monthly": sum(
            (unit.market_rent - unit.contract_rent for unit in occupied), ZERO
        ),
        "concessions_monthly": concessions,
        "economic_occupancy": (contract - concessions) / gpr,
    }
    for unit_type in sorted({unit.unit_type for unit in units}):
        key = quote(unit_type, safe="")
        matching = [unit for unit in units if unit.unit_type == unit_type]
        outputs[f"unit_mix:{key}:units"] = Decimal(len(matching))
        outputs[f"unit_mix:{key}:market_rent"] = sum((unit.market_rent for unit in matching), ZERO)
    return CalcResult(
        calc_id=calc_id,
        fn="normalize_rent_roll",
        inputs={f"unit:{unit.unit_id}": unit.input_id for unit in units},
        outputs=outputs,
        code_version=code_version,
    )
