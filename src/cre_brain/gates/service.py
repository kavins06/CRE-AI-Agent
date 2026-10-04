"""Deterministic gates bound to authenticated scope and canonical tool evidence.

No supplied GateResult is consumed. Missing plans or unavailable dependencies
produce actionable failures. Advisory registrations never invoke a model in v1.
"""

import re
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import Engine

from cre_brain.config.settings import GateSettings
from cre_brain.domain import Assumption, CalcResult, Deliverable, GateResult
from cre_brain.domain.base import TenantScope
from cre_brain.finance.returns import ReturnsInput, calculate_returns
from cre_brain.finance.scenarios import EvaluatedScenario, FragilityInput, assess_fragility
from cre_brain.gates.authority import input_unit, numeric_inputs, output_unit
from cre_brain.gates.catalog import REGISTRY, required_gates
from cre_brain.gates.limits import GateFailure, bounded_decimal, bounded_file, bounded_values
from cre_brain.gates.models import (
    EvidenceRef,
    FinanceRecipe,
    GatePlan,
    GateReport,
    InputProvider,
    NumberToken,
    RuleCheck,
)
from cre_brain.gates.numbers import extract_numbers, has_label, number_context
from cre_brain.gates.presentation import displayed_decimal, visible_text
from cre_brain.gates.state import CanonicalState, GateStore
from cre_brain.rules.engine import evaluate
from cre_brain.rules.models import AssumptionInput, BuyBoxInput, LoiInput, Policy, RuleInput


def _result(failures: list[str], **metrics: Decimal) -> GateResult:
    return GateResult(passed=not failures, failures=failures, metrics=metrics)


def _numeric(value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Canonical evidence must contain a finite Decimal, not a claim string")
    return bounded_decimal(value)


def _display_clause(text: str, position: int) -> str:
    start = 0
    for separator in re.finditer(r"[!?;]|\.(?!\d)|\n[ \t]*\n", text):
        if separator.start() >= position:
            return text[start : separator.start()]
        start = separator.end()
    return text[start:]


def _close(actual: Decimal, expected: Decimal, absolute: Decimal, relative: Decimal) -> bool:
    bounded_values((actual, expected, absolute, relative))
    return abs(Fraction(actual) - Fraction(expected)) <= max(
        Fraction(absolute), Fraction(relative) * abs(Fraction(expected))
    )


class GateService:
    def __init__(
        self,
        engine: Engine,
        *,
        scope: "TenantScope",
        settings: GateSettings,
        inputs: InputProvider,
        scratch: Path,
        as_of: date | None = None,
    ) -> None:
        self.engine = engine
        self.scope = scope
        self.settings = GateSettings.model_validate(settings.model_dump())
        self.inputs = inputs
        self.scratch = scratch
        self.state = CanonicalState(engine, scope, inputs, as_of or datetime.now(UTC).date())

    def for_gate(self, name: str) -> "BoundGate":
        if name not in REGISTRY:
            raise ValueError("unknown_gate")
        return BoundGate(self, name)

    def check(self, gate: str, deliverable: Deliverable) -> GateResult:
        """Check one named gate. The service is the bound SPEC check(deliverable) seam."""
        if gate not in REGISTRY:
            return _result(["unknown_gate"])
        if not REGISTRY[gate].blocking:
            return GateResult(
                passed=False,
                failures=["Advisory not evaluated in v1"],
                metrics={"advisory": Decimal(1), "evaluated": Decimal(0)},
            )
        try:
            try:
                canonical = self.inputs.identity(self.scope, deliverable)
                plan = self.inputs.plan(self.scope, deliverable)
            except Exception:
                raise GateFailure("authority_unavailable") from None
            if canonical is None or plan is None:
                raise GateFailure("authority_unavailable")
            if canonical.model_dump(exclude={"gate_results"}) != deliverable.model_dump(
                exclude={"gate_results"}
            ):
                raise GateFailure("canonical_mismatch")
            deliverable = Deliverable.model_validate(deliverable.model_dump())
            if not deliverable.deal_ids or len(set(deliverable.deal_ids)) != len(
                deliverable.deal_ids
            ):
                raise ValueError("Deliverable requires unique deal identities")
            if deliverable.status in {"stale", "superseded", "blocked"}:
                raise ValueError("Deliverable is stale, superseded or blocked")
            self.state.fresh(deliverable.d_id)
            bounded_values(plan)
            bounded_file(Path(deliverable.path))
            plan = GatePlan.model_validate(plan.model_dump())
            result = self._check(gate, deliverable, plan)
            # Dependency diagnostics may include source values, paths or identities.
            if result.failures:
                return GateResult(
                    passed=False, failures=[f"{gate}: canonical_mismatch"], metrics=result.metrics
                )
            return result
        except (
            Exception
        ) as error:  # Gate dependencies must fail closed, including unavailable backends.
            category = error.category if isinstance(error, GateFailure) else "invalid_evidence"
            return _result([f"{gate}: {category}"])

    def check_all(self, deliverable: Deliverable) -> GateReport:
        try:
            canonical = self.inputs.identity(self.scope, deliverable)
            plan = self.inputs.plan(self.scope, deliverable)
            if canonical is None or plan is None:
                raise GateFailure("authority_unavailable")
        except Exception:  # Required gates are still emitted when evidence loading fails.
            # Refuse independently of the caller-selected catalog on authority failure.
            result = _result(["number_provenance: authority_unavailable"])
            return GateReport(
                results={"number_provenance": result}, blocking_failures=("number_provenance",)
            )
        names = required_gates(canonical.kind, extraction=plan.extraction)
        results = {name: self.check(name, deliverable) for name in names}
        return GateReport(
            results=results,
            blocking_failures=tuple(
                name
                for name, result in results.items()
                if REGISTRY[name].blocking and not result.passed
            ),
        )

    def _check(self, gate: str, d: Deliverable, plan: GatePlan) -> GateResult:
        if gate == "coverage":
            return self._coverage(d, plan)
        if gate == "checksums":
            return self._checksums(d, plan)
        if gate in {"parity", "excel_errors"}:
            return self._workbook(d, plan)
        if gate in {"buy_box", "assumption_ranges", "policy_bands"}:
            if gate == "assumption_ranges":
                self._assumptions(d, plan)
            return self._rules(gate, d, plan)
        if gate == "irr_sanity":
            return self._returns(d, plan)
        if gate == "fragility":
            return self._fragility(d, plan)
        text = self._text(d, plan)
        if gate == "required_sections":
            return self._sections(self._text(d, plan, visible=True), plan)
        return self._numbers(text, d, plan, match_model=gate == "numbers_match_model")

    def _text(self, d: Deliverable, plan: GatePlan, *, visible: bool = False) -> str:
        path = Path(d.path)
        bounded_file(path)
        if path.suffix.lower() == ".xlsx":
            # Numbers in real workbooks are checked by mapped integrity, not by
            # regex over binary OOXML. Text cells must still have number evidence.
            if plan.workbook is None:
                raise ValueError("Workbook numeric extraction requires a trusted mapping")
            mapped = {entry.address for entry in plan.workbook.mapping.entries}
            formula_book = load_workbook(path, data_only=False)
            try:
                for sheet in formula_book:
                    if sheet.max_row * sheet.max_column > 20000:
                        raise GateFailure("resource_limit")
                    for row in sheet:
                        for cell in row:
                            if (
                                isinstance(cell.value, (int, float, Decimal, date, datetime))
                                or cell.data_type == "f"
                            ) and (f"{sheet.title}!{cell.coordinate}" not in mapped):
                                raise ValueError("Unmapped substantive workbook number/formula")
            finally:
                formula_book.close()
            book = load_workbook(path, data_only=True)
            lines = []
            try:
                for sheet in book:
                    for row in sheet:
                        for cell in row:
                            if cell.row is None or cell.column is None:
                                continue
                            hidden = (
                                sheet.sheet_state != "visible"
                                or sheet.row_dimensions[cell.row].hidden
                                or any(
                                    dim.hidden
                                    and (dim.min or 1) <= cell.column <= (dim.max or 16384)
                                    for dim in sheet.column_dimensions.values()
                                )
                            )
                            if isinstance(cell.value, str) and cell.data_type != "e":
                                lines.append(
                                    " " * len(cell.value) if visible and hidden else cell.value
                                )
                            if cell.hyperlink and cell.hyperlink.target:
                                target = cell.hyperlink.target
                                lines.append(" " * len(target) if visible and hidden else target)
            finally:
                book.close()
            return "\n".join(lines)
        if path.suffix.lower() not in {".md", ".txt", ".csv"}:
            raise ValueError("Unsupported deliverable format; no safe numeric extractor available")
        return path.read_text(encoding="utf-8")

    def _coverage(self, d: Deliverable, plan: GatePlan) -> GateResult:
        if not plan.coverage or len({f.name for f in plan.coverage}) != len(plan.coverage):
            raise ValueError("Coverage needs an unambiguous trusted field/checklist inventory")
        for field in plan.coverage:
            seen = set()
            for ref in field.references:
                self.state.resolve(ref, d)
                if ref.kind != "fact" or ref.record_id in seen or ref.key != field.name:
                    raise ValueError(
                        "Coverage requires unique canonical facts for the required field"
                    )
                seen.add(ref.record_id)
                fact = self.state.fact(ref.record_id, ref.deal_id)
                if not any(
                    p.doc_id == field.doc_id
                    and (p.page is not None or (p.sheet is not None and p.cell is not None))
                    for p in fact.provenance
                ):
                    raise ValueError(f"Coverage field {field.name} lacks required source location")
        return _result([], covered_fields=Decimal(len(plan.coverage)))

    def _checksums(self, d: Deliverable, plan: GatePlan) -> GateResult:
        if not plan.checksums or len({c.name for c in plan.checksums}) != len(plan.checksums):
            raise ValueError("Checksums need a typed trusted reconciliation inventory")
        failures = []
        for checksum in plan.checksums:
            refs = (*checksum.parts, checksum.total)
            identities = [(r.kind, r.record_id, r.key) for r in refs]
            if len(set(identities)) != len(identities) or len({r.deal_id for r in refs}) != 1:
                raise ValueError("Checksum parts and total need distinct identities in one deal")
            if any(r.unit != checksum.unit for r in refs):
                raise ValueError("Checksum references have incompatible units")
            total = _numeric(self.state.resolve(checksum.total, d))
            parts = sum(
                (Fraction(_numeric(self.state.resolve(r, d))) for r in checksum.parts), Fraction(0)
            )
            if checksum.unit in {"count", "days", "year"}:
                absolute, relative = Fraction(0), Fraction(0)
                if any(
                    _numeric(self.state.resolve(r, d))
                    != _numeric(self.state.resolve(r, d)).to_integral_value()
                    for r in refs
                ):
                    raise ValueError("Count/day/year checksums require integral evidence")
            elif checksum.unit == "ratio":
                absolute, relative = Fraction(0), Fraction(self.settings.number_rel)
            elif checksum.unit in {
                "USD",
                "USD/month",
                "USD/year",
                "EUR",
                "GBP",
                "CAD",
                "AUD",
                "CHF",
                "JPY",
            }:
                absolute, relative = Fraction(self.settings.checksum_abs), Fraction(0)
            else:
                raise ValueError("Unsupported typed checksum tolerance unit")
            if abs(parts - Fraction(total)) > max(absolute, relative * abs(Fraction(total))):
                failures.append(f"{checksum.name}: parts do not reconcile to canonical total")
        return _result(failures, checked_sums=Decimal(len(plan.checksums)))

    def _workbook(self, d: Deliverable, plan: GatePlan) -> GateResult:
        from cre_brain.excel.parity import check_parity
        from cre_brain.excel.writer import build_workbook

        if plan.workbook is None or plan.workbook.deal_id not in d.deal_ids:
            raise ValueError("Required trusted workbook template/map/deal identity unavailable")
        w = plan.workbook
        bounded_file(w.template)
        bounded_file(Path(d.path))
        # Validate source authority and magnitudes before the writer does finance.
        self._workbook_numbers(d, plan)
        # Regenerate authoritative expectations through the existing product path,
        # including current-input recomputation. Never trust serialized descriptors.
        self.scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.scratch) as directory:
            build = build_workbook(
                w.template,
                w.mapping,
                Path(directory) / "reference.xlsx",
                engine=self.engine,
                scope=self.scope,
                deal_id=w.deal_id,
                task_id=d.d_id,
                calculations=w.calculations,
                gates=self.settings,
                as_of=self.state.as_of,
            )
            return check_parity(
                Path(d.path), build.expected, gates=self.settings, mapping=build.mapping
            )

    def _workbook_numbers(self, d: Deliverable, plan: GatePlan) -> None:
        assert plan.workbook is not None
        w = plan.workbook
        verified_calcs = {}
        input_pins: set[tuple[str, int, str, str]] = set()
        for entry in w.mapping.entries:
            if entry.source == "calc":
                assert entry.calculation is not None
                recipe = self.inputs.recipe(
                    self.scope, w.deal_id, w.calculations[entry.calculation]
                )
                if recipe is None or not recipe.dependencies:
                    raise GateFailure("authority_unavailable")
                input_pins.update(
                    (r.record_id, r.version, r.key, r.unit)
                    for r in recipe.dependencies.values()
                    if r.kind == "fact"
                )
        template = load_workbook(w.template, data_only=False)
        display = load_workbook(d.path, data_only=False)
        values = load_workbook(d.path, data_only=True)
        try:
            for sheet in template:
                if sheet.max_row * sheet.max_column > 20000:
                    raise GateFailure("resource_limit")
                for row in sheet:
                    for original in row:
                        address = f"{sheet.title}!{original.coordinate}"
                        if address not in {e.address for e in w.mapping.entries}:
                            if original.value != display[sheet.title][original.coordinate].value:
                                raise GateFailure("unsupported_display")
            for entry in w.mapping.entries:
                if entry.source == "fact":
                    fact = self.state.fact_for_key(entry.key, w.deal_id)
                    if fact.unit != entry.unit:
                        raise GateFailure("canonical_mismatch")
                    if (fact.fact_id, fact.version, fact.key, fact.unit) not in input_pins:
                        raise GateFailure("canonical_mismatch")
                    canonical = _numeric(fact.value)
                else:
                    if entry.calculation is None:
                        raise GateFailure("authority_unavailable")
                    identity = w.calculations[entry.calculation]
                    if identity not in verified_calcs:
                        verified_calcs[identity] = self.state.calc(identity, w.deal_id)
                    calc = verified_calcs[identity]
                    ref = EvidenceRef(
                        kind="calc",
                        record_id=calc.calc_id,
                        deal_id=w.deal_id,
                        key=entry.key,
                        function=entry.function,
                        unit=entry.unit,
                    )
                    self._calc_unit(ref, plan)
                    canonical = _numeric(calc.outputs[entry.key])
                cell = display[entry.sheet][entry.cell]
                original = template[entry.sheet][entry.cell]
                # Preserve the trusted native template's format; reject unsupported
                # formats even in a host template rather than infer visible semantics.
                fmt = cell.number_format
                if (
                    fmt != original.number_format
                    or not re.fullmatch(r"0(?:\.0+)?%?", fmt)
                    or ("%" in fmt and entry.unit != "ratio")
                    or cell.is_date
                ):
                    raise GateFailure("unsupported_display")
                if entry.source == "fact":
                    # Source labels/units are part of the mapped input display.
                    for neighbor in display[entry.sheet][cell.row]:
                        if neighbor.column != cell.column:
                            if neighbor.value != template[entry.sheet][neighbor.coordinate].value:
                                raise GateFailure("unsupported_display")
                raw = values[entry.sheet][entry.cell].value
                if isinstance(raw, bool) or not isinstance(raw, (int, float, Decimal)):
                    raise GateFailure("unsupported_display")
                actual = bounded_decimal(Decimal(str(raw)))
                displayed = displayed_decimal(actual, fmt, entry.unit)
                if entry.role == "input":
                    matches = (
                        actual == canonical
                        and displayed == canonical
                        and actual.is_signed() == canonical.is_signed()
                        and displayed.is_signed() == canonical.is_signed()
                    )
                else:
                    token = NumberToken(
                        start=0, end=1, raw="", value=displayed, unit=entry.unit, display_unit=fmt
                    )
                    matches = self._number_matches(token, canonical, entry.unit)
                if not matches:
                    raise GateFailure("canonical_mismatch")
        finally:
            template.close()
            display.close()
            values.close()

    def _model(self, d: Deliverable, plan: GatePlan) -> FinanceRecipe:
        model = plan.model
        if model is None or model.deal_id not in d.deal_ids:
            raise GateFailure("authority_unavailable")
        bounded_file(model.artifact)
        if sha256(model.artifact.read_bytes()).hexdigest() != model.sha256:
            raise GateFailure("canonical_mismatch")
        self.state.calc(model.calc_id, model.deal_id)
        recipe = self.inputs.recipe(self.scope, model.deal_id, model.calc_id)
        if (
            recipe is None
            or recipe.code_version != model.code_version
            or recipe.model_id != model.model_id
            or recipe.model_version != model.model_version
        ):
            raise GateFailure("canonical_mismatch")
        return FinanceRecipe.model_validate(recipe.model_dump())

    def _assumptions(self, d: Deliverable, plan: GatePlan) -> None:
        recipe = self._model(d, plan)
        assert plan.model is not None
        values = numeric_inputs(recipe)
        inventory = plan.model.assumptions
        if (
            set(inventory) != set(values)
            or not inventory
            or len(plan.assumptions) != len(inventory)
            or set(c.model_dump_json() for c in plan.assumptions)
            != set(c.model_dump_json() for c in inventory.values())
            or len({c.record_id for c in inventory.values()}) != len(inventory)
        ):
            raise GateFailure("authority_unavailable")
        store = GateStore(self.engine, Assumption)
        text = visible_text(self._text(d, plan, visible=True))
        for field, check in inventory.items():
            record = store.get(check.record_id, scope=self.scope)
            if (
                record is None
                or record.value != values[field]
                or check.unit != input_unit(recipe, field)
            ):
                raise GateFailure("canonical_mismatch")
            if record.is_proxy:
                if not any(
                    has_label(line, "proxy") and has_label(line, record.key.replace("_", " "))
                    for line in text.splitlines()
                    if "<!--" not in line
                ):
                    raise GateFailure("unsupported_display")
        if plan.assumption_ranges is None:
            raise GateFailure("authority_unavailable")
        growth = plan.assumption_ranges.references.get("rent_growth")
        if growth is None or self.state.resolve(growth, d) != values.get("annual_revenue_growth"):
            raise GateFailure("canonical_mismatch")
        for check in plan.assumptions:
            self.state.fresh(check.record_id)
            if check.deal_id not in d.deal_ids:
                raise ValueError("Assumption is outside deliverable deal scope")
            record = store.get(check.record_id, scope=self.scope)
            pinned = store.get(check.record_id, scope=self.scope, version=check.version)
            if record is None or pinned != record:
                raise ValueError("Assumption is missing or superseded")
            record = Assumption.model_validate(record.model_dump())
            if (
                record.as_of > self.state.as_of
                or not record.sources
                or not record.rationale.strip()
            ):
                raise ValueError(
                    "Assumption requires current dated canonical sources and rationale"
                )
            bounded_values(record)
            low, value, high = (_numeric(v) for v in (record.low, record.value, record.high))
            if not low <= value <= high:
                raise ValueError("Canonical assumption is outside its declared low/high range")
            for identity in record.sources:
                self.state.fresh(identity)
                if self.state.facts.get(identity, scope=self.scope) is not None:
                    fact = self.state.fact(identity, check.deal_id)
                    if fact.key != record.key or fact.unit != check.unit or fact.value != value:
                        raise ValueError("Assumption key/value/unit differs from canonical source")
                else:
                    calc = self.state.calc(identity, check.deal_id)
                    if calc.outputs.get(record.key) != value:
                        raise ValueError("Assumption value differs from canonical calculation")

    def _rules(self, gate: str, d: Deliverable, plan: GatePlan) -> GateResult:
        schemas: dict[
            str, tuple[type[RuleInput], str, RuleCheck | None, Policy, dict[str, str], str]
        ] = {
            "buy_box": (
                BuyBoxInput,
                "buy_box.default",
                plan.buy_box,
                plan.buy_box_policy,
                {"units": "count", "dscr": "ratio", "price": "USD", "market_tier": "text"},
                "eligible",
            ),
            "assumption_ranges": (
                AssumptionInput,
                "assumption_ranges.mf",
                plan.assumption_ranges,
                plan.assumption_policy,
                {
                    "market_tier": "text",
                    "asset_class": "text",
                    "vintage": "year",
                    "rent_growth": "ratio",
                    "cap_rate": "ratio",
                },
                "within_policy",
            ),
            "policy_bands": (
                LoiInput,
                "loi_policy.default",
                plan.policy_bands,
                plan.loi_policy,
                {
                    "price": "USD",
                    "dd_days": "days",
                    "close_days": "days",
                    "deposit_percent": "ratio",
                    "financing_contingency": "bool",
                },
                "within_policy",
            ),
        }
        model, table, check, policy, units, accepted = schemas[gate]
        if check is None or set(check.references) != set(units):
            raise ValueError("Required canonical rule fields unavailable or ambiguous")
        if len({r.deal_id for r in check.references.values()}) != 1:
            raise ValueError("Rule inputs must refer to one coherent deal")
        values: dict[str, object] = {}
        for key, ref in check.references.items():
            if ref.key != key or ref.unit != units[key]:
                raise ValueError(f"Rule field {key} requires its canonical key and unit")
            value: object = self.state.resolve(ref, d)
            if units[key] in {"count", "days", "year"}:
                numeric = _numeric(value)
                if numeric != numeric.to_integral_value():
                    raise ValueError("Rule count/day/year field must be integral")
                value = int(numeric)
            values[key] = value
        item = model.model_validate(
            {
                **values,
                "policy": policy,
                "source_ids": tuple(r.record_id for r in check.references.values()),
            }
        )
        decision = evaluate(table, item).decision
        if gate == "buy_box" and decision.classification == "ineligible":
            recommendations = re.findall(
                r"^Recommendation:\s*(GO|NO_GO)\s*$", self._text(d, plan), re.MULTILINE
            )
            if recommendations == ["NO_GO"]:
                return _result([], evaluated=Decimal(1), eligible=Decimal(0))
        return _result(
            []
            if decision.classification == accepted
            else [f"{decision.reason_code}: {decision.classification}"],
            evaluated=Decimal(1),
        )

    def _returns(self, d: Deliverable, plan: GatePlan) -> GateResult:
        if not plan.returns:
            raise ValueError("IRR sanity requires canonical returns inputs and calculations")
        for check in plan.returns:
            ref = check.reference
            self.state.resolve(ref, d)
            source = self.inputs.finance_input(self.scope, ref.deal_id, check.input_id)
            if not isinstance(source, ReturnsInput):
                raise ValueError("Required canonical cash flows unavailable")
            bounded_values(source)
            source = ReturnsInput.model_validate(source.model_dump())
            calc = self.state.calc(ref.record_id, ref.deal_id)
            recomputed = calculate_returns(
                source, calc_id=calc.calc_id, code_version=calc.code_version
            )
            if calc != recomputed:
                raise ValueError(
                    "Stored return calculation differs from canonical finance recomputation"
                )
            if calc.outputs["undefined"] or calc.outputs["infinitely_many_roots"]:
                raise ValueError("IRR is undefined or infinitely ambiguous; escalation required")
            if calc.outputs["ambiguous"] and (
                "irr" in calc.outputs or "xirr" in calc.outputs or "mirr" not in calc.outputs
            ):
                raise ValueError(
                    "Multiple IRR roots require the finance contract's MIRR disclosure"
                )
            if calc.outputs["ambiguous"]:
                self._return_disclosure(calc, d, plan)
                if not self._numbers(self._text(d, plan), d, plan, match_model=False).passed:
                    raise GateFailure("canonical_mismatch")
        return _result([], checked_returns=Decimal(len(plan.returns)))

    def _return_disclosure(self, calc: "CalcResult", d: Deliverable, plan: GatePlan) -> None:
        visible = visible_text(self._text(d, plan, visible=True))
        classification = (
            r"^\s*(?:(?:multiple|ambiguous)\s+IRR\s+roots|"
            r"IRR\s+classification:\s*(?:multiple|ambiguous)\s+roots)\s*(?:[.;:]|$)"
        )
        classification_match = re.search(classification, visible, re.I | re.M)
        if not classification_match:
            raise GateFailure("unsupported_display")
        if not re.fullmatch(
            r"\s*(?:(?:multiple|ambiguous)\s+IRR\s+roots|"
            r"IRR\s+classification:\s*(?:multiple|ambiguous)\s+roots)\s*",
            _display_clause(visible, classification_match.start()),
            re.I,
        ):
            raise GateFailure("unsupported_display")
        fallback = False
        for match in re.finditer(r"MIRR\s+(?:fallback|reported fallback)", visible, re.I):
            if not re.fullmatch(
                r"\s*MIRR\s+(?:fallback|reported fallback)\s+"
                r"(?:(?:is\s+)?reported|[+\-−]?(?:\d+(?:\.\d+)?|\.\d+)"
                r"(?:e[+\-]?\d+)?\s*(?:%|percent))\s*",
                _display_clause(visible, match.start()),
                re.I,
            ):
                raise GateFailure("unsupported_display")
            fallback = True
        if not fallback:
            raise GateFailure("unsupported_display")
        required = {k for k in calc.outputs if k.startswith("root:")} | {
            "mirr",
            "root_count",
        }
        cited = {
            c.reference.key
            for c in plan.citations
            if c.reference.kind == "calc" and c.reference.record_id == calc.calc_id
        }
        visible_keys = {
            c.reference.key
            for c in plan.citations
            if c.reference.record_id == calc.calc_id and re.search(r"\d", visible[c.start : c.end])
        }
        if not required.issubset(cited & visible_keys):
            raise GateFailure("unsupported_display")

    def _fragility(self, d: Deliverable, plan: GatePlan) -> GateResult:
        check = plan.fragility
        if check is None or check.deal_id not in d.deal_ids or check.base.deal_id != check.deal_id:
            raise ValueError("Required canonical fragility input unavailable")
        source = self.inputs.finance_input(self.scope, check.deal_id, check.input_id)
        if not isinstance(source, FragilityInput):
            raise ValueError("Fragility requires a canonical typed policy and P10-P90 ranges")
        bounded_values(source)
        source = FragilityInput.model_validate(source.model_dump())
        if (
            source.fragility_margin != self.settings.fragility_margin
            or check.base.key != source.metric_key
        ):
            raise ValueError("Fragility metric/margin differs from configured finance policy")
        base_recipe = self._model(d, plan)
        if (
            base_recipe.calc_id != check.base.record_id
            or plan.model is None
            or plan.model.deal_id != check.deal_id
        ):
            raise GateFailure("canonical_mismatch")
        self.state.fresh(source.input_id)
        self.state.resolve(check.base, d)
        base = self.state.calc(check.base.record_id, check.deal_id)
        scenarios = []
        for scenario in check.scenarios:
            if scenario.result.deal_id != check.deal_id or scenario.result.key != source.metric_key:
                raise ValueError("Fragility scenario metric/deal mismatch")
            self.state.fresh(scenario.input_id)
            self.state.resolve(scenario.result, d)
            values = {
                key: _numeric(self.state.resolve(ref, d))
                for key, ref in scenario.assumptions.items()
            }
            if any(
                ref.deal_id != check.deal_id
                or ref.key not in {key, scenario.input_id}
                or ref.unit != "ratio"
                for key, ref in scenario.assumptions.items()
            ):
                raise ValueError(
                    "Scenario assumption references require compatible identities/units"
                )
            result = self.state.calc(scenario.result.record_id, check.deal_id)
            recipe = self.inputs.recipe(self.scope, check.deal_id, result.calc_id)
            if (
                recipe is None
                or recipe.source.input_id != scenario.input_id
                or recipe.model_id != base_recipe.model_id
                or recipe.model_version != base_recipe.model_version
                or recipe.code_version != base_recipe.code_version
                or recipe.function != base_recipe.function
                or recipe.scenario_parameters != base_recipe.scenario_parameters
                or set(recipe.scenario_parameters) != set(values)
                or set(values) != {r.name for r in source.ranges}
            ):
                raise GateFailure("canonical_mismatch")
            base_structure = base_recipe.source.model_dump(exclude={"input_id"})
            scenario_structure = recipe.source.model_dump(exclude={"input_id"})
            for field in recipe.scenario_parameters.values():
                base_structure.pop(field, None)
                scenario_structure.pop(field, None)
            if base_structure != scenario_structure:
                raise GateFailure("canonical_mismatch")
            parameters = numeric_inputs(recipe)
            base_parameters = numeric_inputs(base_recipe)
            if (
                set(parameters) != set(base_parameters)
                or any(
                    parameters.get(field) != values[name]
                    for name, field in recipe.scenario_parameters.items()
                )
                or any(
                    base_parameters.get(
                        r.name if r.name in base_parameters else recipe.scenario_parameters[r.name]
                    )
                    != r.base
                    for r in source.ranges
                )
                or any(
                    parameters[k] != base_parameters[k]
                    for k in parameters
                    if k not in recipe.scenario_parameters.values()
                )
            ):
                raise GateFailure("canonical_mismatch")
            scenarios.append(
                EvaluatedScenario(
                    input_id=scenario.input_id,
                    assumptions=values,
                    result=self.state.calc(scenario.result.record_id, check.deal_id),
                )
            )
        result = assess_fragility(
            source, base, tuple(scenarios), calc_id="gate-fragility", code_version="gate-validation"
        )
        conditional = bool(result.outputs["conditional"])
        return _result(
            ["Recommendation requires CONDITIONAL: joint in-range downside flips below margin"]
            if conditional and d.status != "conditional"
            else [],
            **result.outputs,
        )

    def _sections(self, text: str, plan: GatePlan) -> GateResult:
        if not plan.required_sections or len(set(plan.required_sections)) != len(
            plan.required_sections
        ):
            raise ValueError("Required firm section inventory unavailable or ambiguous")
        text = visible_text(text)
        sections: dict[str, str] = {}
        current: str | None = None
        fenced = False
        for line in text.splitlines():
            if re.match(r"^\s*(```|~~~)", line):
                fenced = not fenced
                continue
            if fenced or line.startswith((">", "    ")):
                continue
            heading = re.fullmatch(r"#{1,6}\s+(.+?)\s*#*\s*", line)
            if heading:
                current = heading[1].casefold().strip()
                if current in sections:
                    raise ValueError("Ambiguous duplicate required-section heading")
                sections[current] = ""
            elif current:
                sections[current] += line.strip()
        failures = [
            f"Missing or empty required section: {name}"
            for name in plan.required_sections
            if not re.search(r"[^\W_]", sections.get(name.casefold().strip(), ""))
        ]
        return _result(failures, required_sections=Decimal(len(plan.required_sections)))

    def _numbers(
        self, text: str, d: Deliverable, plan: GatePlan, *, match_model: bool
    ) -> GateResult:
        if Path(d.path).suffix.lower() == ".xlsx":
            parity = self._workbook(d, plan)
            if not parity.passed:
                return parity
        numbers = extract_numbers(text)
        if match_model and not plan.model_bindings:
            raise ValueError("Required contextual canonical model bindings unavailable")
        if match_model:
            recipe = self._model(d, plan)
            for key, binding in plan.model_bindings.items():
                if (
                    binding.kind != "calc"
                    or binding.key != key
                    or binding.record_id != recipe.calc_id
                    or (plan.model is not None and binding.deal_id != plan.model.deal_id)
                ):
                    raise ValueError(
                        "Contextual model bindings require canonical calculation outputs"
                    )
                self.state.resolve(binding, d)
                self._calc_unit(binding, plan)
        citations = {(c.start, c.end): c.reference for c in plan.citations}
        if len(citations) != len(plan.citations) or set(citations) != {
            (n.start, n.end) for n in numbers
        }:
            raise ValueError(
                "Every numeric occurrence needs exactly one identity citation; no surplus spans"
            )
        failures = []
        for number in numbers:
            ref = citations[(number.start, number.end)]
            raw_value = self.state.resolve(ref, d)
            if ref.kind == "calc":
                self._calc_unit(ref, plan)
                calc = self.state.calc(ref.record_id, ref.deal_id)
                if calc.fn == "calculate_returns" and ref.key in {
                    "irr",
                    "xirr",
                    "mirr",
                    "reported_return",
                }:
                    if calc.outputs["undefined"] or calc.outputs["infinitely_many_roots"]:
                        raise GateFailure("unsupported_display")
                    if calc.outputs["ambiguous"]:
                        self._return_disclosure(calc, d, plan)
            context = number_context(text, number)
            labels = plan.labels.get(ref.key, (ref.key.replace("_", " "),))
            self._claim_context(context, ref, d, plan)
            if not any(has_label(context, label) for label in labels):
                failures.append(
                    f"{number.start}: numeric evidence is unrelated to its semantic context"
                )
                continue
            if match_model:
                model_ref = plan.model_bindings.get(ref.key)
                if model_ref is None or model_ref != ref or ref.kind != "calc":
                    failures.append(f"{number.start}: missing contextual canonical model reference")
                    continue
            if number.date_value is not None:
                matches = ref.unit == "date" and raw_value == number.date_value
            else:
                matches = self._number_matches(number, _numeric(raw_value), ref.unit)
            if not matches:
                failures.append(
                    f"{number.start}: display value/unit differs from canonical "
                    f"{ref.record_id}:{ref.key}"
                )
        return _result(failures, extracted_numbers=Decimal(len(numbers)))

    def _claim_context(
        self, context: str, ref: EvidenceRef, d: Deliverable, plan: GatePlan
    ) -> None:
        if len(d.deal_ids) > 1:
            if not has_label(context, ref.deal_id) or any(
                has_label(context, deal) for deal in d.deal_ids if deal != ref.deal_id
            ):
                raise GateFailure("canonical_mismatch")
        labels = plan.labels.get(ref.key, (ref.key.replace("_", " "),))
        residual = context
        for label in labels:
            residual = re.sub(re.escape(label), "", residual, flags=re.I)
        metrics = {
            "price",
            "occupancy",
            "units",
            "rent growth",
            "cap rate",
            "dscr",
            "noi",
            "yield",
            "irr",
            "rent",
            "growth",
        }
        if any(has_label(residual, metric) for metric in metrics):
            raise GateFailure("canonical_mismatch")
        period = ref.period
        if ref.kind == "fact":
            fact = self.state.fact(ref.record_id, ref.deal_id)
            if fact.valid_time is not None:
                dates = [
                    day.isoformat()
                    for day in (fact.valid_time.start, fact.valid_time.end)
                    if day is not None
                ]
                expected = "/".join(dates)
                if period != expected:
                    raise GateFailure("canonical_mismatch")
        else:
            match = re.match(r"(month|year):(\d+):", ref.key)
            if match:
                expected = f"{match[1]} {match[2]}"
                if period != expected:
                    raise GateFailure("canonical_mismatch")
        if period is not None and not has_label(context, period):
            raise GateFailure("canonical_mismatch")
        if period is None and re.search(
            r"\b(?:prior|current|previous|next|reporting)\s+(?:period|year|month)\b", context, re.I
        ):
            raise GateFailure("canonical_mismatch")

    def _calc_unit(self, ref: EvidenceRef, plan: GatePlan) -> None:
        if ref.function is None or ref.unit != output_unit(ref.function, ref.key):
            raise GateFailure("canonical_mismatch")

    def _number_matches(self, number: NumberToken, value: Decimal, unit: str) -> bool:
        if unit in {"text", "bool"} or (number.unit != "number" and number.unit != unit):
            return False
        if number.unit == "number" and unit not in {
            "ratio",
            "count",
            "days",
            "year",
            "number",
            "sqft",
        }:
            return False
        # No dollar-sized slack for ratios/counts. Dollar slack also cannot make
        # a positive display match a canonical negative value (or the reverse).
        if number.value.is_signed() != value.is_signed() or (number.value == 0) != (value == 0):
            return False
        if unit == "ratio":
            absolute, relative = Decimal(0), self.settings.number_rel
        elif unit in {"count", "days", "year", "number", "sqft"}:
            absolute, relative = Decimal(0), Decimal(0)
        elif unit in {
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
        }:
            absolute, relative = self.settings.number_abs, self.settings.number_rel
        else:
            return False
        return _close(number.value, value, absolute, relative)


class BoundGate:
    """SPEC check(deliverable) interface, bound to authenticated service state."""

    def __init__(self, service: GateService, name: str) -> None:
        self.service = service
        self.name = name

    def check(self, deliverable: Deliverable) -> GateResult:
        return self.service.check(self.name, deliverable)
