"""Host-only deterministic composition, with T032 Excel build/recalc delegation."""

from pathlib import Path

from pydantic import ValidationError

from cre_brain.domain import CalcResult
from cre_brain.runner.policy import HostContext, Limits, Refusal, charge
from cre_brain.runner.tools import files
from cre_brain.runner.tools.registry import ToolRegistry

from .calculations import compose
from .evidence import inspect_evidence
from .models import UWModel, UWQuestion, UWRefusal, UWRequest, UWWorkbook


def refused(error: Refusal) -> UWRefusal:
    return UWRefusal(
        code=error.category,
        questions=(
            UWQuestion(
                field=error.message if error.category == "missing_inputs" else "underwriting",
                text=error.message,
            ),
        ),
    )


class UWCore:
    """Called by trusted host code; not registered as an analyst command yet."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def compose(self, request: UWRequest) -> UWModel | UWRefusal:
        try:
            context = HostContext.model_validate(self.registry.context.model_dump(warnings=False))
            limits = Limits.model_validate(self.registry.limits.model_dump(warnings=False))
            with self.registry.transaction() as state:
                charge(state, context, limits)
                try:
                    if context.role not in {"lead", "user"}:
                        raise Refusal("unauthorized_role", "Host must authenticate a lead or user.")
                    request = UWRequest.model_validate(request.model_dump(warnings=False))
                    with state.connection.begin_nested():
                        result = compose(state, request)
                        self.registry.deadline(state)
                    return result
                except Refusal as error:
                    return refused(error)
                except (ValidationError, ValueError, ArithmeticError):
                    return refused(
                        Refusal("invalid_input", "Refresh canonical input types, ranges and units.")
                    )
        except Refusal as error:
            return refused(error)
        except (ValidationError, ValueError, ArithmeticError):
            return refused(
                Refusal("invalid_input", "Refresh canonical input types, ranges and units.")
            )

    def workbook(self, model: UWModel) -> UWWorkbook | UWRefusal:
        try:
            model = UWModel.model_validate(model.model_dump(warnings=False))
            if (
                model.deal_id != self.registry.context.deal_id
                or model.task_id != self.registry.context.task_id
            ):
                raise Refusal(
                    "incompatible_evidence", "Use this authenticated task's Python model."
                )
            if tuple(c.component for c in model.calculations) != ("proforma",):
                raise Refusal(
                    "unsupported_workbook",
                    "mf_standard cannot mirror optional schedules, debt or returns; "
                    "host needs a reviewed template extension.",
                )
            with self.registry.transaction() as state:
                current = inspect_evidence(
                    state, [c.numbers[0].reference for c in model.calculations]
                )
                if current != model.evidence:
                    raise Refusal(
                        "stale_evidence", "Recompose the Python model from current evidence."
                    )
                calc = model.calculation("proforma")
                stored = state.current(CalcResult, calc.calc_id)
                if stored is None or stored.model_dump_json(warnings=False) != calc.record_json:
                    raise Refusal(
                        "untrusted_evidence", "Python snapshot differs from stored calculation."
                    )
                binding = state.binding(calc.calc_id, "calc")
                assert binding is not None
                expected_numbers = {
                    key: (value, binding["units"][key]) for key, value in stored.outputs.items()
                }
                actual_numbers = {
                    n.reference.key: (n.value, n.reference.unit)
                    for n in calc.numbers
                    if n.reference.kind == "calc"
                    and n.reference.record_id == calc.calc_id
                    and n.reference.version == 1
                }
                if (
                    expected_numbers != actual_numbers
                    or len(calc.numbers) != len(expected_numbers)
                    or calc.code_version != stored.code_version
                ):
                    raise Refusal("untrusted_evidence", "Model numbers differ from stored outputs.")
                inputs = binding.get("field_references", {})
                if any(r["kind"] != "fact" for r in inputs.values()):
                    raise Refusal(
                        "unsupported_workbook",
                        "mf_standard requires mapped facts; "
                        "assumptions need a reviewed mapping extension.",
                    )
                source = binding.get("finance_input", {})
                if source.get("projection_months") != 60:
                    raise Refusal("unsupported_workbook", "mf_standard mirrors exactly 60 months.")
            if self.registry.excel_engine is None:
                raise Refusal(
                    "missing_provider", "Host must configure the existing Excel recalc engine."
                )
            built = self.registry.call(
                "excel_build", {"template": "mf_standard", "calculation": calc.calc_id}
            )
            if built["status"] != "ok":
                raise Refusal(built["category"], built["message"])
            identity = built["data"]["artifact_id"]
            recalculated = self.registry.call("excel_recalc_parity", {"artifact_id": identity})
            if recalculated["status"] != "ok":
                raise Refusal(recalculated["category"], recalculated["message"])
            if not recalculated["data"]["parity"]["passed"]:
                raise Refusal(
                    "parity_failed", "Recalculated workbook failed existing complete parity."
                )
            with self.registry.transaction() as state:
                binding = state.binding(identity, "workbook")
                assert binding is not None
                # The existing handler records the recalculated digest, not the saved path.
                # Locate the engine's saved file inside this exclusive artifact directory.
                path = Path(binding["descriptor"]["path"])
                gates = [
                    e
                    for e in state.history()
                    if e.kind == "gate_result" and e.payload.get("artifact_id") == identity
                ]
                digest = gates[-1].payload["digest"]
                if not isinstance(digest, str):
                    raise Refusal("untrusted_artifact", "Stored digest must be a string.")
                matches = [
                    p
                    for p in path.parent.glob("*.xlsx")
                    if files.digest(files.read(self.registry.workspace, p)) == digest
                ]
                if len(matches) != 1:
                    raise Refusal(
                        "untrusted_artifact",
                        "Host must identify one recalculated artifact by its stored digest.",
                    )
                return UWWorkbook(artifact_id=identity, path=matches[0], sha256=digest)
        except Refusal as error:
            return refused(error)
        except (ValidationError, ValueError, ArithmeticError):
            return refused(
                Refusal("invalid_input", "Refresh the canonical Python model and template.")
            )
