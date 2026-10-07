from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cre_brain.finance.rentroll import RentRollUnit, normalize_rent_roll


def unit(
    name: str, kind: str, market: str, contract: str, occupied: bool, concession: str = "0"
) -> RentRollUnit:
    return RentRollUnit(
        unit_id=name,
        input_id=f"fact-{name}",
        unit_type=kind,
        market_rent=Decimal(market),
        contract_rent=Decimal(contract),
        occupied=occupied,
        monthly_concession=Decimal(concession),
    )


def test_t013_ac1_rentroll_computes_occupancy_gpr_loss_concessions_and_mix() -> None:
    result = normalize_rent_roll(
        [
            unit("101", "1br", "1000", "900", True, "50"),
            unit("102", "1br", "1000", "0", False),
            unit("201", "2br", "1500", "1400", True),
        ],
        calc_id="rr-1",
        code_version="release-1",
    )
    assert result.inputs == {"unit:101": "fact-101", "unit:102": "fact-102", "unit:201": "fact-201"}
    assert result.outputs == {
        "total_units": Decimal(3),
        "occupied_units": Decimal(2),
        "physical_occupancy": Decimal(2) / Decimal(3),
        "gpr_monthly": Decimal("3500"),
        "loss_to_lease_monthly": Decimal("200"),
        "concessions_monthly": Decimal("50"),
        "economic_occupancy": Decimal("2250") / Decimal("3500"),
        "unit_mix:1br:units": Decimal(2),
        "unit_mix:1br:market_rent": Decimal("2000"),
        "unit_mix:2br:units": Decimal(1),
        "unit_mix:2br:market_rent": Decimal("1500"),
    }


def test_t013_ac1_rentroll_refuses_ambiguous_or_impossible_rows() -> None:
    with pytest.raises(ValueError):
        normalize_rent_roll([], calc_id="rr", code_version="v")
    with pytest.raises(ValueError):
        normalize_rent_roll(
            [unit("101", "1br", "1000", "1100", True)], calc_id="rr", code_version="v"
        )
    with pytest.raises(ValueError):
        normalize_rent_roll(
            [unit("101", "1br", "1000", "900", True), unit("101", "1br", "1000", "900", True)],
            calc_id="rr",
            code_version="v",
        )


@given(st.lists(st.tuples(st.integers(1, 5000), st.booleans()), min_size=1, max_size=50))
def test_t013_ac3_rentroll_totals_and_occupancy_invariants(rows) -> None:
    units = [
        unit(str(index), "unit", str(rent), str(rent if occupied else 0), occupied)
        for index, (rent, occupied) in enumerate(rows)
    ]
    result = normalize_rent_roll(units, calc_id="rr", code_version="v")
    assert result.outputs["gpr_monthly"] == sum((u.market_rent for u in units), Decimal())
    assert Decimal() <= result.outputs["physical_occupancy"] <= Decimal(1)
    assert Decimal() <= result.outputs["economic_occupancy"] <= Decimal(1)
