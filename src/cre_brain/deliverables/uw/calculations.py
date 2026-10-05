"""Exact-reference composition of the existing deterministic finance functions."""

import hashlib
from collections.abc import Callable, Mapping
from datetime import date
from fractions import Fraction
from typing import Any, Literal

from cre_brain.domain import CalcResult
from cre_brain.finance.debt import DebtSizingInput, LoanTerms, size_debt
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.finance.returns import ReturnsInput
from cre_brain.finance.taxes import TaxAssessment, TaxReassessmentRule, reassess_taxes
from cre_brain.finance.valueadd import ValueAddPlan, build_value_add_schedule
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools.contracts import FinanceRun, Reference
from cre_brain.runner.tools.evidence import number, resolve
from cre_brain.runner.tools.finance import SCHEMAS, run
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.state import ToolState, fingerprint

from .evidence import core_version, inspect_evidence
from .models import CalculationSnapshot, ModelNumber, UWModel, UWRequest

PROFORMA_UNITS = SCHEMAS["build_proforma"][2]
TAX_UNITS = {
    "sale_price": "USD",
    "current_assessed_value": "USD",
    "current_annual_tax": "USD",
    "assessment_ratio": "ratio",
    "millage": "mills",
    "phase_in_years": "count",
    "annual_growth_cap": "ratio",
    "full_reassessment": "bool",
    "operating_expenses_exclude_property_tax": "bool",
}
VALUE_ADD_UNITS = {
    "total_units": "count",
    "units_per_month": "count",
    "start_month": "count",
    "downtime_months": "count",
    "cost_per_unit": "USD/unit",
    "current_monthly_rent_per_unit": "USD/unit/month",
    "monthly_rent_premium": "USD/unit/month",
    "ramp_months": "count",
}
DEBT_UNITS = {
    "property_value": "USD",
    "max_ltv": "ratio",
    "min_dscr": "ratio",
    "min_debt_yield": "ratio",
    "base_rate": "ratio",
    "spread": "ratio",
    "term_months": "count",
    "amortization_months": "count",
    "io_months": "count",
    "fee_rate": "ratio",
    "fixed_fee": "USD",
    "prepayment_rate": "ratio",
}


def fields(args: Mapping[str, Any], units: Mapping[str, str], component: str) -> None:
    if len(args) > len(units):
        raise Refusal("unsupported_inputs", f"{component}: use only supported explicit inputs.")
    missing = set(units) - set(args)
    if missing:
        raise Refusal("missing_inputs", f"{component}: provide {', '.join(sorted(missing))}.")
    if set(args) != set(units):
        raise Refusal("unsupported_inputs", f"{component}: use only supported explicit inputs.")


def validate_shape(request: UWRequest) -> None:
    for component, args, units in (
        ("proforma", request.proforma, PROFORMA_UNITS),
        ("taxes", request.taxes, TAX_UNITS),
        ("value_add", request.value_add, VALUE_ADD_UNITS),
        ("debt", request.debt, DEBT_UNITS),
    ):
        if args is not None:
            fields(args, units, component)
    if request.returns is None:
        return
    returns = request.returns
    if returns.fn != "calculate_returns":
        raise Refusal("unsupported_inputs", "Returns requires calculate_returns references.")
    units = {**SCHEMAS["calculate_returns"][2]}
    if "dates" in returns.args:
        units["dates"] = "date"
    fields(returns.args, units, "returns")
    flows = returns.args["cash_flows"]
    if not isinstance(flows, list) or not 2 <= len(flows) <= 600:
        raise Refusal("invalid_input", "Returns requires 2 to 600 ordered cash-flow references.")
    for key, raw in returns.args.items():
        if key == "dates":
            if not isinstance(raw, list) or len(raw) != len(flows):
                raise Refusal("invalid_input", "Every cash flow needs one ordered date reference.")
        elif key != "cash_flows" and isinstance(raw, list):
            raise Refusal("invalid_input", "Scalar finance fields require one reference.")


def values(
    state: ToolState, args: dict[str, Reference | None], units: dict[str, str], component: str
) -> dict[str, Any]:
    fields(args, units, component)
    result: dict[str, Any] = {}
    for key, ref in args.items():
        if ref is None:
            if component != "taxes" or key != "annual_growth_cap":
                raise Refusal("missing_inputs", f"{component}.{key}: supply a canonical reference.")
            result[key] = None  # Explicit uncapped jurisdiction rule, never an inferred default.
        elif units[key] == "bool":
            result[key] = resolve(state, ref)
            if ref.unit != "bool" or type(result[key]) is not bool:
                raise Refusal("incompatible_evidence", f"{component}.{key}: supply a boolean fact.")
        else:
            value = number(state, ref, units[key])
            if units[key] == "count":
                if value != value.to_integral_value():
                    raise Refusal("invalid_input", f"{component}.{key}: supply an integral count.")
                result[key] = int(value)
            else:
                result[key] = value
    return result


def validate_returns(state: ToolState, request: FinanceRun) -> None:
    flows = request.args["cash_flows"]
    finance_rate = request.args["finance_rate"]
    reinvest_rate = request.args["reinvest_rate"]
    assert isinstance(flows, list)
    assert isinstance(finance_rate, Reference) and isinstance(reinvest_rate, Reference)
    dates = None
    if "dates" in request.args:
        raw_dates = request.args["dates"]
        assert isinstance(raw_dates, list)
        dates = tuple(resolve(state, ref) for ref in raw_dates)
        if any(ref.unit != "date" for ref in raw_dates) or any(type(d) is not date for d in dates):
            raise Refusal("incompatible_evidence", "Dated returns require canonical date facts.")
    source = ReturnsInput(
        input_id="uw-returns",
        cash_flows=tuple(number(state, ref, "USD") for ref in flows),
        finance_rate=number(state, finance_rate, "ratio"),
        reinvest_rate=number(state, reinvest_rate, "ratio"),
        dates=dates,
    )
    # Match the library's existing nonconventional IRR support bound before
    # execution. Exact aggregation preserves cancellation and repeated dates.
    periods = (
        [(day - min(source.dates)).days for day in source.dates]
        if source.dates is not None
        else list(range(len(source.cash_flows)))
    )
    totals: dict[int, Fraction] = {}
    for period, amount in zip(periods, source.cash_flows, strict=True):
        totals[period] = totals.get(period, Fraction(0)) + Fraction(amount)
    signs = [amount > 0 for _, amount in sorted(totals.items()) if amount]
    if len(signs) > 128 and sum(a != b for a, b in zip(signs, signs[1:], strict=False)) > 1:
        raise Refusal(
            "invalid_input",
            "Nonconventional IRR supports at most 128 distinct nonzero periods/dates.",
        )


def persist(
    state: ToolState,
    fn: str,
    refs: Mapping[str, Reference | None],
    execute: Callable[[str, str], CalcResult],
) -> CalcResult:
    version = core_version()
    manifest = {k: r.model_dump(mode="json") if r is not None else None for k, r in refs.items()}
    sources = {k: r for k, r in refs.items() if r is not None}
    identity = (
        "calc-"
        + hashlib.sha256(
            canonical(
                {
                    "deal": state.context.deal_id,
                    "fn": fn,
                    "code": version,
                    "refs": manifest,
                }
            ).encode()
        ).hexdigest()
    )
    calculated = execute(identity, version)
    result = CalcResult(
        calc_id=identity,
        fn=fn,
        inputs={k: r.record_id for k, r in sources.items()},
        outputs=calculated.outputs,
        code_version=version,
    )
    existing = state.current(CalcResult, identity)
    if len(state.records(CalcResult, identity)) > 1 or (
        existing is not None and existing != result
    ):
        raise Refusal(
            "ambiguous_evidence", "Stored identity differs from deterministic calculation."
        )
    if existing is None:
        state.append(result)
        for ref in sources.values():
            state.edge(ref.record_id, identity)
        units = dict.fromkeys(result.outputs, "USD")
        if fn == "reassess_taxes":
            units["assessment_floor_applied"] = "number"
        elif fn == "build_value_add_schedule":
            for key in units:
                if key.endswith(("units", "units_turned", "premium_units_equivalent")):
                    units[key] = "count"
        elif fn == "size_debt":
            for key in ("dscr", "dscr_defined", "dscr_limit_binding_possible"):
                if key in units:
                    units[key] = "ratio" if key == "dscr" else "number"
        state.event(
            "tool_result",
            {
                "binding": "calc",
                "identity": identity,
                "deal": state.context.deal_id,
                "digest": fingerprint(result),
                "code_version": version,
                "references": [r.model_dump(mode="json") for r in sources.values()],
                "field_references": manifest,
                "units": units,
                "composition": "uw-core",
            },
        )
    inspect_evidence(state, [reference(result, next(iter(result.outputs)), state)])
    return result


def reference(calc: CalcResult, key: str, state: ToolState) -> Reference:
    binding = state.binding(calc.calc_id, "calc")
    assert binding is not None
    return Reference(
        kind="calc", record_id=calc.calc_id, version=1, key=key, unit=binding["units"][key]
    )


def compose(state: ToolState, request: UWRequest) -> UWModel:
    validate_shape(request)
    # Verify every requested dependency before creating any calculation.
    refs = [*request.proforma.values()]
    for group in (request.taxes, request.value_add, request.debt):
        if group is not None:
            refs.extend(r for r in group.values() if r is not None)
    if request.returns:
        for item in request.returns.args.values():
            refs.extend(item if isinstance(item, list) else [item])
    inspect_evidence(state, refs)
    inputs = values(state, dict(request.proforma), PROFORMA_UNITS, "proforma")
    months = inputs["projection_months"]
    proforma_input = ProFormaInput(input_id="uw-proforma", **inputs)
    tax_input = (
        values(state, request.taxes, TAX_UNITS, "taxes") if request.taxes is not None else None
    )
    va_input = (
        values(state, dict(request.value_add), VALUE_ADD_UNITS, "value_add")
        if request.value_add is not None
        else None
    )
    debt_input = (
        values(state, dict(request.debt), DEBT_UNITS, "debt") if request.debt is not None else None
    )
    plan = None
    if va_input is not None:
        plan = ValueAddPlan(input_id="uw-value-add", **va_input)
        if plan.start_month > months:
            raise Refusal("invalid_input", "Projection must include the renovation start month.")
        # Months are bounded by ProFormaInput (360). No count controls an
        # unbounded loop: units affect cohort count; downtime/ramp are arithmetic.
        cohorts = (plan.total_units + plan.units_per_month - 1) // plan.units_per_month
        if cohorts > 600:
            raise Refusal(
                "unsupported_inputs",
                "Value-add supports at most 600 renovation cohorts; provide a supported plan.",
            )
    terms = None
    if debt_input is not None:
        terms = LoanTerms(
            input_id="uw-loan-terms",
            **{k: v for k, v in debt_input.items() if k in LoanTerms.model_fields},
        )
    if request.returns is not None:
        validate_returns(state, request.returns)
    components: list[tuple[Any, CalcResult]] = []
    taxes = value_add = None
    if tax_input is not None:
        if not tax_input.pop("operating_expenses_exclude_property_tax"):
            raise Refusal(
                "ambiguous_tax_basis", "Provide operating expenses excluding property tax."
            )
        assessment = TaxAssessment(
            input_id="uw-assessment",
            **{
                k: tax_input.pop(k)
                for k in ("sale_price", "current_assessed_value", "current_annual_tax")
            },
        )
        rule = TaxReassessmentRule(input_id="uw-tax-rule", **tax_input)
        assert request.taxes is not None
        tax_refs = dict(request.taxes)
        tax_refs["projection_months"] = request.proforma["projection_months"]
        taxes = persist(
            state,
            "reassess_taxes",
            tax_refs,
            lambda cid, cv: reassess_taxes(
                assessment,
                rule=rule,
                projection_years=(months + 11) // 12,
                calc_id=cid,
                code_version=cv,
            ),
        )
        components.append(("taxes", taxes))
    if plan is not None:
        assert request.value_add is not None
        va_refs = {**request.value_add, "projection_months": request.proforma["projection_months"]}
        value_add = persist(
            state,
            "build_value_add_schedule",
            va_refs,
            lambda cid, cv: build_value_add_schedule(
                plan, projection_months=months, calc_id=cid, code_version=cv
            ),
        )
        components.append(("value_add", value_add))
    if taxes is None and value_add is None:
        proforma = run(state, FinanceRun(fn="build_proforma", args=dict(request.proforma)))
    else:
        proforma_refs = dict(request.proforma)
        if taxes:
            proforma_refs["tax_schedule"] = reference(taxes, "target_annual_tax", state)
        if value_add:
            proforma_refs["value_add_schedule"] = reference(
                value_add, "total_renovation_cost", state
            )
        proforma = persist(
            state,
            "build_proforma",
            proforma_refs,
            lambda cid, cv: build_proforma(
                proforma_input, taxes=taxes, value_add=value_add, calc_id=cid, code_version=cv
            ),
        )
    components.append(("proforma", proforma))
    if debt_input is not None:
        if months < 12:
            raise Refusal("missing_inputs", "Debt sizing needs a complete first year of NOI.")
        sizing_keys = ("property_value", "max_ltv", "min_dscr", "min_debt_yield")
        sizing = DebtSizingInput(
            input_id="uw-sizing",
            annual_noi=proforma.outputs["year:1:noi"],
            **{k: debt_input.pop(k) for k in sizing_keys},
        )
        assert terms is not None
        assert request.debt is not None
        debt_refs = {**request.debt, "annual_noi": reference(proforma, "year:1:noi", state)}
        debt = persist(
            state,
            "size_debt",
            debt_refs,
            lambda cid, cv: size_debt(sizing, terms, calc_id=cid, code_version=cv),
        )
        components.append(("debt", debt))
    irr_status: LiteralIRR = "not_requested"
    if request.returns:
        returns = run(state, request.returns)
        components.append(("returns", returns))
        irr_status = (
            "unique"
            if returns.outputs["unique"]
            else "ambiguous"
            if returns.outputs["ambiguous"]
            else "undefined"
        )
    snapshots_list = []
    for component, calc in components:
        binding = state.binding(calc.calc_id, "calc")
        assert binding is not None
        snapshots_list.append(
            CalculationSnapshot(
                component=component,
                calc_id=calc.calc_id,
                code_version=calc.code_version,
                record_json=calc.model_dump_json(warnings=False),
                numbers=tuple(
                    ModelNumber(
                        value=value,
                        reference=Reference(
                            kind="calc",
                            record_id=calc.calc_id,
                            version=1,
                            key=key,
                            unit=binding["units"][key],
                        ),
                    )
                    for key, value in sorted(calc.outputs.items())
                ),
            )
        )
    snapshots = tuple(snapshots_list)
    evidence = inspect_evidence(state, [calc.numbers[0].reference for calc in snapshots])
    return UWModel(
        deal_id=state.context.deal_id,
        task_id=state.context.task_id,
        calculations=snapshots,
        evidence=evidence,
        irr_status=irr_status,
    )


LiteralIRR = Literal["not_requested", "unique", "ambiguous", "undefined"]
