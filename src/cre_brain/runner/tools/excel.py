"""Trusted mapped reference build and deterministic recalc/parity handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from cre_brain.config.settings import GateSettings
from cre_brain.domain import CalcResult, Fact, GateResult
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import ExcelBuild, ExcelRecalc, Reference, Template
from cre_brain.runner.tools.evidence import resolve
from cre_brain.runner.tools.registry import ToolRegistry, ok
from cre_brain.runner.tools.state import ToolState


def build_excel(registry: ToolRegistry, state: ToolState, request: ExcelBuild) -> dict[str, Any]:
    from cre_brain.excel.writer import build_workbook

    if request.template != "mf_standard":
        raise Refusal(
            "invalid_input", "Use the host-verified mapped mf_standard reference template."
        )
    template = registry.inputs.template(registry.context, request.template)
    if template is None:
        raise Refusal(
            "missing_provider", "Host must register the trusted reference template and map."
        )
    template = Template.model_validate(template.model_dump(warnings=False))
    if template.path.suffix != ".xlsx" or template.path.resolve() != template.path:
        raise Refusal(
            "unauthorized_path",
            "Trusted template must be a regular .xlsx without symlink ancestors.",
        )
    if files.digest(files.read(template.path.parent, template.path)) != template.sha256:
        raise Refusal("untrusted_artifact", "Reference template changed; host must revalidate it.")
    calc = state.current(CalcResult, request.calculation)
    binding = state.binding(request.calculation, "calc")
    if calc is None or binding is None or calc.fn != "build_proforma":
        raise Refusal(
            "untrusted_evidence",
            "Excel requires a canonical stored reference proforma calculation.",
        )
    for source in binding["references"]:
        ref = Reference.model_validate(source)
        if ref.kind != "fact":
            raise Refusal(
                "incompatible_evidence",
                "Reference Excel template currently requires mapped canonical facts.",
            )
        resolve(state, ref)
    # Validate every mapped fact, including conflicts/duplicates omitted by a calc.
    from sqlalchemy import select

    from cre_brain.state.schema import metadata
    from cre_brain.state.store import tenant_filter

    table = metadata.tables["facts"]
    ids = (
        state.connection.execute(
            select(table.c.record_id).where(tenant_filter(table, registry.context.scope)).distinct()
        )
        .scalars()
        .all()
    )
    facts = [state.current(Fact, i) for i in ids]
    for entry in template.mapping.entries:
        if entry.source == "fact":
            matches = [
                f
                for f in facts
                if f and f.deal_id == registry.context.deal_id and f.key == entry.key
            ]
            if len(matches) != 1:
                raise Refusal(
                    "ambiguous_evidence",
                    "Reference template requires one current canonical fact per mapped key.",
                )
            fact = matches[0]
            assert fact is not None
            resolve(
                state,
                Reference(
                    kind="fact",
                    record_id=fact.fact_id,
                    version=fact.version,
                    key=fact.key,
                    unit=entry.unit,
                ),
            )
    resolve(
        state,
        Reference(kind="calc", record_id=calc.calc_id, version=1, key="month:1:noi", unit="USD"),
    )
    identity = "workbook-" + uuid4().hex
    parts = ("deals", registry.context.deal_id, "deliverables", identity)
    with files.directory(registry.workspace, parts, create=True):
        pass
    target = registry.workspace.joinpath(*parts, "model.xlsx")
    # Reserve exclusively before passing the private output to deterministic Excel code.
    files.write(registry.workspace, (*parts, "model.xlsx"), b"")
    build = build_workbook(
        template.path,
        template.mapping,
        target,
        engine=registry.engine,
        scope=registry.context.scope,
        deal_id=registry.context.deal_id,
        task_id=registry.context.task_id,
        calculations={"proforma": calc.calc_id},
        gates=registry.settings.gates,
    )
    state.event(
        "tool_result",
        {
            "binding": "workbook",
            "identity": identity,
            "deal": registry.context.deal_id,
            "task": registry.context.task_id,
            "digest": files.digest(files.read(registry.workspace, target)),
            "descriptor": build.model_dump(mode="json", warnings=False),
            "calculation": calc.calc_id,
        },
    )
    return ok({"artifact_id": identity})


def recalc_excel(registry: ToolRegistry, state: ToolState, request: ExcelRecalc) -> dict[str, Any]:
    from cre_brain.excel.deliverable import recalc_deliverable
    from cre_brain.excel.models import WorkbookBuild

    binding = state.binding(request.artifact_id, "workbook")
    if (
        not binding
        or binding["deal"] != registry.context.deal_id
        or binding["task"] != registry.context.task_id
    ):
        raise Refusal(
            "untrusted_artifact", "Use a workbook identity built by this scoped tool server."
        )
    if registry.excel_engine is None:
        raise Refusal(
            "missing_provider", "Host must configure an isolated trusted Excel recalc engine."
        )
    build = WorkbookBuild.model_validate(binding["descriptor"])
    if files.digest(files.read(registry.workspace, build.path)) != binding["digest"]:
        raise Refusal(
            "untrusted_artifact",
            "Workbook changed; rebuild canonical inputs before recalculation.",
        )
    resolve(
        state,
        Reference(
            kind="calc",
            record_id=binding["calculation"],
            version=1,
            key="month:1:noi",
            unit="USD",
        ),
    )
    trusted_engine = registry.excel_engine

    class ScopedEngine:
        def recalc(self, path: Path) -> Path:
            output = trusted_engine.recalc(path)
            # Validate the host engine's output BEFORE the parity library opens it.
            files.relative(build.path.parent, output)
            files.read(registry.workspace, output)
            return output

    output, result = recalc_deliverable(
        build,
        ScopedEngine(),
        gates=GateSettings.model_validate(registry.settings.gates.model_dump(warnings=False)),
    )
    files.relative(build.path.parent, output)
    digest = files.digest(files.read(registry.workspace, output))
    result = GateResult.model_validate(result.model_dump(warnings=False))
    state.event(
        "gate_result",
        {
            "artifact_id": request.artifact_id,
            "parity": result.model_dump(mode="json", warnings=False),
            "digest": digest,
        },
    )
    return ok(
        {
            "artifact_id": request.artifact_id,
            "parity": result.model_dump(mode="json", warnings=False),
        }
    )
