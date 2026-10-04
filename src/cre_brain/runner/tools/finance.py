"""Explicit finance whitelist; every numeric input is a canonical identity."""

import hashlib
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from cre_brain.domain import CalcResult
from cre_brain.finance.exit import ExitInput, calculate_exit
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.finance.returns import (
    CashOnCashInput,
    NPVInput,
    ReturnsInput,
    calculate_returns,
    cash_on_cash,
    excel_npv,
)
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools.contracts import FinanceRun, Reference
from cre_brain.runner.tools.evidence import number
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.state import ToolState, fingerprint

# Actual finance functions only. Complex debt/tax/waterfall contracts can be added
# with field-specific units; arbitrary import names or Python execution are forbidden.
SCHEMAS: dict[str, tuple[type[BaseModel], Callable[..., CalcResult], dict[str, str]]] = {
    "calculate_exit": (
        ExitInput,
        calculate_exit,
        {
            "forward_noi": "USD",
            "cap_rate": "ratio",
            "selling_cost_rate": "ratio",
            "fixed_selling_cost": "USD",
            "debt_payoff": "USD",
        },
    ),
    "build_proforma": (
        ProFormaInput,
        build_proforma,
        {
            "base_monthly_revenue": "USD/month",
            "base_monthly_operating_expenses": "USD/month",
            "annual_revenue_growth": "ratio",
            "annual_expense_growth": "ratio",
            "vacancy_rate": "ratio",
            "credit_loss_rate": "ratio",
            "monthly_reserves": "USD/month",
            "projection_months": "count",
        },
    ),
    "calculate_returns": (
        ReturnsInput,
        calculate_returns,
        {"cash_flows": "USD", "finance_rate": "ratio", "reinvest_rate": "ratio"},
    ),
    "excel_npv": (NPVInput, excel_npv, {"cash_flows": "USD", "discount_rate": "ratio"}),
    "cash_on_cash": (
        CashOnCashInput,
        cash_on_cash,
        {"annual_operating_cash_flow": "USD", "invested_equity": "USD"},
    ),
}


def output_units(fn: str, outputs: dict[str, Any]) -> dict[str, str]:
    if fn in {"calculate_exit", "build_proforma"}:
        return dict.fromkeys(outputs, "USD")
    if fn == "excel_npv":
        return {key: "USD" if key == "npv" else "number" for key in outputs}
    if fn == "cash_on_cash":
        return dict.fromkeys(outputs, "ratio")
    result = {}
    for key in outputs:
        if key in {"total_contributions", "total_distributions"}:
            result[key] = "USD"
        elif key in {"root_count", "pyxirr_verified_roots"}:
            result[key] = "count"
        elif key in {
            "unique",
            "ambiguous",
            "undefined",
            "infinitely_many_roots",
            "pyxirr_supported",
            "equity_multiple_defined",
            "mirr_defined",
        }:
            result[key] = "number"
        else:
            result[key] = "ratio"
    return result


def run(state: ToolState, request: FinanceRun) -> CalcResult:
    if request.fn not in SCHEMAS:
        raise Refusal("unknown_function", "Select a supported deterministic finance function.")
    model, function, units = SCHEMAS[request.fn]
    expected = set(units)
    if request.fn == "calculate_returns":
        expected |= {"dates"} if "dates" in request.args else set()
    if set(request.args) != expected:
        raise Refusal(
            "invalid_input", "Provide exactly the canonical references required by this function."
        )
    values: dict[str, Any] = {}
    refs: list[Reference] = []
    from cre_brain.runner.tools.evidence import resolve

    for field, raw in request.args.items():
        group = raw if isinstance(raw, list) else [raw]
        if not group or len(group) > 600:
            raise Refusal("invalid_input", "Finance sequences need 1 to 600 stored references.")
        refs.extend(group)
        if field == "dates":
            from datetime import date

            dates = [resolve(state, ref) for ref in group]
            if any(ref.unit != "date" for ref in group) or any(type(v) is not date for v in dates):
                raise Refusal(
                    "incompatible_evidence", "Dated returns require canonical date facts."
                )
            values[field] = tuple(dates)
            continue
        numbers = [number(state, ref, units[field]) for ref in group]
        if field == "projection_months":
            if len(numbers) != 1 or numbers[0] != numbers[0].to_integral_value():
                raise Refusal(
                    "invalid_input", "Projection months requires one integral stored count."
                )
            values[field] = int(numbers[0])
        elif field == "cash_flows":
            if not isinstance(raw, list):
                raise Refusal("invalid_input", "Cash flows require an ordered reference list.")
            values[field] = tuple(numbers)
        else:
            if isinstance(raw, list):
                raise Refusal("invalid_input", "Scalar finance fields require one reference.")
            values[field] = numbers[0]
    # Hash actual whitelisted finance implementation files, including arithmetic helpers.
    from pathlib import Path

    import cre_brain.finance

    files = sorted(Path(cre_brain.finance.__file__).parent.glob("*.py"))
    code_version = hashlib.sha256(
        b"".join(p.name.encode() + p.read_bytes() for p in files)
    ).hexdigest()
    identity_data = {
        "deal": state.context.deal_id,
        "fn": request.fn,
        "args": request.model_dump(mode="json", warnings=False)["args"],
        "code": code_version,
    }
    calc_id = "calc-" + hashlib.sha256(canonical(identity_data).encode()).hexdigest()
    source = model.model_validate({"input_id": calc_id, **values})
    result = function(source, calc_id=calc_id, code_version=code_version)
    result = CalcResult.model_validate(
        {
            **result.model_dump(warnings=False),
            "inputs": {
                f"{field}:{index}": ref.record_id
                for field, raw in request.args.items()
                for index, ref in enumerate(raw if isinstance(raw, list) else [raw])
            },
        }
    )
    existing = state.current(CalcResult, calc_id)
    if len(state.records(CalcResult, calc_id)) > 1:
        raise Refusal("ambiguous_evidence", "Calculation identity has multiple stored versions.")
    if existing is not None and existing != result:
        raise Refusal(
            "ambiguous_evidence", "Stored calculation differs from deterministic recomputation."
        )
    if existing is None:
        state.append(result)
        for ref in refs:
            state.edge(ref.record_id, calc_id)
        state.event(
            "tool_result",
            {
                "binding": "calc",
                "identity": calc_id,
                "deal": state.context.deal_id,
                "digest": fingerprint(result),
                "code_version": code_version,
                "finance_input": source.model_dump(mode="json", warnings=False),
                "field_references": request.model_dump(mode="json", warnings=False)["args"],
                "references": [r.model_dump(mode="json", warnings=False) for r in refs],
                "units": output_units(request.fn, result.outputs),
            },
        )
    return result
