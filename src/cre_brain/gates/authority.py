"""Reproduce whitelisted finance recipes over immutable host inputs and pins."""

from decimal import Decimal

from cre_brain.domain import CalcResult
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.finance.returns import ReturnsInput, calculate_returns
from cre_brain.finance.risk import RiskInput, risk_score
from cre_brain.gates.limits import GateFailure, bounded_values
from cre_brain.gates.models import FinanceRecipe


def numeric_inputs(recipe: FinanceRecipe) -> dict[str, Decimal]:
    fields = recipe.source.model_dump()
    result = {key: value for key, value in fields.items() if isinstance(value, Decimal)}
    if isinstance(recipe.source, ProFormaInput):
        result["projection_months"] = Decimal(recipe.source.projection_months)
    if isinstance(recipe.source, ReturnsInput):
        result.update({f"cash_flows:{i}": v for i, v in enumerate(recipe.source.cash_flows)})
    return result


def reproduce(recipe: FinanceRecipe) -> CalcResult:
    bounded_values(recipe)
    recipe = FinanceRecipe.model_validate(recipe.model_dump())
    if isinstance(recipe.source, ReturnsInput):
        result = calculate_returns(
            recipe.source, calc_id=recipe.calc_id, code_version=recipe.code_version
        )
    elif isinstance(recipe.source, ProFormaInput):
        result = build_proforma(
            recipe.source, calc_id=recipe.calc_id, code_version=recipe.code_version
        )
    elif isinstance(recipe.source, RiskInput):
        result = risk_score(recipe.source, calc_id=recipe.calc_id, code_version=recipe.code_version)
    else:
        raise GateFailure("authority_unavailable")
    if recipe.dependencies:
        required = set(numeric_inputs(recipe))
        # Projection horizon may be an immutable host constant rather than a fact.
        # It remains part of the complete model assumption inventory.
        if set(recipe.dependencies) not in (required, required - {"projection_months"}):
            raise GateFailure("authority_unavailable")
        dependencies = {key: ref.record_id for key, ref in recipe.dependencies.items()}
        if isinstance(recipe.source, RiskInput):
            dependencies = {key + ":0": value for key, value in dependencies.items()}
            dependencies["policy"] = recipe.source.input_id
        result = result.model_copy(update={"inputs": dependencies})
    bounded_values(result)
    return result


def input_unit(recipe: FinanceRecipe, key: str) -> str:
    if isinstance(recipe.source, RiskInput):
        return "ratio"
    if key == "projection_months":
        return "count"
    if isinstance(recipe.source, ReturnsInput):
        return "USD" if key.startswith("cash_flows:") else "ratio"
    return "ratio" if "growth" in key or "rate" in key else "USD/month"


def output_unit(function: str, key: str) -> str:
    if function == "risk_score" and key == "risk_score":
        return "ratio"
    if function == "build_proforma":
        return "USD"
    if function != "calculate_returns":
        raise GateFailure("authority_unavailable")
    if key in {"total_contributions", "total_distributions"}:
        return "USD"
    if key in {"root_count", "pyxirr_verified_roots"}:
        return "count"
    if key in {
        "unique",
        "ambiguous",
        "undefined",
        "infinitely_many_roots",
        "pyxirr_supported",
        "equity_multiple_defined",
        "mirr_defined",
    }:
        return "number"
    return "ratio"
