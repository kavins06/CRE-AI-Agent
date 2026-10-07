"""Deterministic host composition over canonical T032 facts/tools and T037 gates."""

from decimal import Decimal
from time import monotonic_ns
from typing import Literal

from cre_brain.deliverables.screen.classify import RuleDecisionModel
from cre_brain.deliverables.screen.inputs import ScreenInputs
from cre_brain.deliverables.screen.models import Classification, Document, ScreenRequest, ScreenRun
from cre_brain.domain import CalcResult, ClaimType, Deliverable, DeliverableKind, Fact, Question
from cre_brain.finance.risk import RiskInput
from cre_brain.gates import GateService, TrustedInputs
from cre_brain.gates.limits import bounded_values
from cre_brain.gates.models import (
    CoverageField,
    EvidenceRef,
    FinanceRecipe,
    GatePlan,
    MemoPair,
    NumberCitation,
    RuleCheck,
)
from cre_brain.gates.numbers import extract_numbers
from cre_brain.rules.engine import evaluate
from cre_brain.rules.models import BuyBoxInput, BuyBoxPolicy
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import Artifact, ArtifactCompanion, Reference
from cre_brain.runner.tools.evidence import screen_fact
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry

# Host vocabulary, never labels taken from model/seller input. No title or quote rendering.
UNITS = {
    "price": "USD",
    "units": "count",
    "dscr": "ratio",
    "occupancy": "ratio",
    "market_tier": "text",
    "noi": "USD",
    "gpr": "USD/year",
}
REQUIRED = ("price", "units", "dscr", "market_tier", "occupancy")


def evidence(ref: Reference, fact: Fact) -> EvidenceRef:
    period = None
    if fact.valid_time is not None:
        period = "/".join(d.isoformat() for d in (fact.valid_time.start, fact.valid_time.end) if d)
    return EvidenceRef(
        kind="fact",
        record_id=ref.record_id,
        version=ref.version,
        deal_id=fact.deal_id,
        key=ref.key,
        unit=ref.unit,
        period=period,
    )


class ScreenService:
    """Host-only composition. No SCREEN tool accepts configuration, authority or verdicts.

    The host provides already-ingested fact pins and authenticated document metadata.
    This source path deliberately has no dependency on an extraction API or model.
    """

    def __init__(
        self, registry: ToolRegistry, authority: TrustedInputs, buy_box: BuyBoxPolicy
    ) -> None:
        if not isinstance(registry.inputs, ScreenInputs):
            raise ValueError("Host must compose ScreenInputs over its canonical tool provider")
        if not isinstance(registry.gates, GateService) or registry.gates.inputs is not authority:
            raise ValueError("SCREEN requires the canonical GateService and its trusted authority")
        if registry.gates.scope != registry.context.scope:
            raise ValueError("SCREEN gate authority must match the authenticated tenant")
        self.registry, self.authority = registry, authority
        self.inputs = registry.inputs
        self.buy_box = BuyBoxPolicy.model_validate(buy_box.model_dump())

    def run(
        self, *, documents: tuple[Document, ...], headlines: dict[str, Reference], run_id: str
    ) -> ScreenRun:
        started = monotonic_ns()
        request = ScreenRequest(run_id=run_id, documents=documents, headlines=headlines)
        context = self.registry.context
        identity = "screen-" + files.digest(
            canonical(
                [
                    context.scope.model_dump(),
                    context.task_id,
                    context.deal_id,
                    context.release_id,
                    run_id,
                ]
            ).encode()
        )
        with self.registry.transaction() as state:
            if any(e.payload.get("screen_start_id") == identity for e in state.history()):
                raise Refusal(
                    "idempotency_conflict", "Use a new SCREEN run identity for regeneration."
                )
            state.event("tool_result", {"screen_start_id": identity, "deal": context.deal_id})
        outcome = "refused"
        try:
            result = self._build(request, identity)
            outcome = "draft" if result.recommendation != "UNKNOWN" else "unknown"
        finally:
            # Real wall duration from a monotonic clock, including failure paths.
            # One stored measurement is used in both the return value and ledger.
            elapsed = monotonic_ns() - started
            with self.registry.transaction() as state:
                state.event(
                    "usage",
                    {
                        "screen_run_id": run_id,
                        "screen_identity": identity,
                        "deal": context.deal_id,
                        "elapsed_ns": elapsed,
                        "clock": "monotonic_ns",
                        "outcome": outcome,
                    },
                )
        return result.model_copy(update={"elapsed_ns": elapsed})

    def _build(self, request: ScreenRequest, identity: str) -> ScreenRun:
        registry = self.registry
        if len({d.doc_id for d in request.documents}) != len(request.documents):
            raise Refusal("ambiguous_evidence", "Document identities must be unique.")
        if any(
            key not in UNITS or ref.key != key or ref.unit != UNITS[key]
            for key, ref in request.headlines.items()
        ):
            raise Refusal("invalid_input", "Provide only canonical headline keys with their units.")
        if any(self.inputs.document(registry.context, d.doc_id) != d for d in request.documents):
            raise Refusal(
                "untrusted_evidence",
                "Host intake must authenticate and pin each document descriptor before SCREEN.",
            )
        classifications = tuple(RuleDecisionModel().classify(d) for d in request.documents)
        kinds = {c.doc_id: c.kind for c in classifications}
        questions = [
            "Clarify document classification"
            for c in classifications
            if c.kind in {"unknown", "ambiguous", "unsupported"}
        ]
        facts: dict[str, Fact] = {}
        with registry.transaction() as state:
            for key, ref in request.headlines.items():
                fact = screen_fact(state, ref)
                bounded_values(fact)
                if fact.valid_time is not None:
                    raise Refusal(
                        "unsupported_period",
                        "SCREEN period displays require standalone canonical date facts; "
                        "this minimal path refuses to invent them.",
                    )
                if any(p.doc_id not in kinds for p in fact.provenance):
                    raise Refusal(
                        "incompatible_evidence",
                        "Headline source is outside this document inventory.",
                    )
                if any(kinds[p.doc_id] not in {"om", "rent_roll", "t12"} for p in fact.provenance):
                    questions.append("Clarify source classification for " + key.replace("_", " "))
                    continue
                if key == "market_tier":
                    if fact.value not in {"A", "B", "C", "unknown"}:
                        raise Refusal(
                            "invalid_input", "Market tier requires a canonical policy tier."
                        )
                elif not isinstance(fact.value, Decimal):
                    raise Refusal("invalid_input", "Numerical headlines require stored Decimals.")
                facts[key] = fact
        for key in REQUIRED:
            if key not in facts or facts[key].value == "unknown":
                questions.append("Provide anchored " + key.replace("_", " "))
        values: dict[str, object] = {
            key: fact.value for key, fact in facts.items() if key in REQUIRED
        }
        if "units" in values:
            units = values["units"]
            if not isinstance(units, Decimal) or units != units.to_integral_value():
                raise Refusal("invalid_input", "Unit count requires an integral canonical Decimal.")
            values["units"] = int(units)
        values.pop("occupancy", None)
        decision = evaluate(
            "buy_box.default",
            BuyBoxInput.model_validate(
                {
                    **values,
                    "policy": self.buy_box,
                    "source_ids": tuple(f.fact_id for f in facts.values()),
                }
            ),
        ).decision
        recommendation: Literal["GO", "NO_GO", "UNKNOWN"] = (
            "GO"
            if decision.classification == "eligible"
            else "NO_GO"
            if decision.classification == "ineligible"
            else "UNKNOWN"
        )
        risk = None
        if registry.risk_policy is None:
            questions.append("Provide a versioned risk policy with provenance")
        if not questions:
            response = registry.call(
                "finance_run",
                {
                    "fn": "risk_score",
                    "args": {
                        k: request.headlines[k].model_dump(mode="json")
                        for k in ("occupancy", "dscr")
                    },
                },
            )
            if response["status"] != "ok":
                raise Refusal(str(response["category"]), str(response["message"]))
            risk = CalcResult.model_validate(response["data"])
            assert registry.risk_policy is not None
            source = RiskInput.model_validate(
                {
                    "input_id": "risk-input-" + risk.calc_id,
                    "occupancy": facts["occupancy"].value,
                    "dscr": facts["dscr"].value,
                    "policy": registry.risk_policy,
                }
            )
            self.authority.put_recipe(
                registry.context.scope,
                registry.context.deal_id,
                FinanceRecipe(
                    calc_id=risk.calc_id,
                    function="risk_score",
                    code_version=risk.code_version,
                    source=source,
                    dependencies={
                        k: evidence(request.headlines[k], facts[k]) for k in ("occupancy", "dscr")
                    },
                ),
            )
        if questions:
            recommendation = "UNKNOWN"
        markdown, citations = self._render(
            facts, request.headlines, classifications, recommendation, risk, questions
        )
        json_memo = {"markdown": markdown}
        bodies = {"md": markdown.encode(), "json": canonical(json_memo).encode()}
        # Exclusive files and unique run identities: never overwrite a published artifact.
        paths = {
            extension: files.write(
                registry.workspace,
                (
                    "deals",
                    registry.context.deal_id,
                    "deliverables",
                    identity,
                    "memo-v1." + extension,
                ),
                data,
            )
            for extension, data in bodies.items()
        }
        pair = MemoPair(
            markdown=paths["md"],
            json_path=paths["json"],
            markdown_sha256=files.digest(bodies["md"]),
            json_sha256=files.digest(bodies["json"]),
        )
        dependencies = [f.fact_id for f in facts.values()] + ([risk.calc_id] if risk else [])
        ids = []
        with registry.transaction() as state:
            for index, text in enumerate(dict.fromkeys(questions)):
                question = Question(
                    q_id=identity + ":q:" + str(index),
                    task_id=registry.context.task_id,
                    deal_id=registry.context.deal_id,
                    text=text,
                    why_it_matters="SCREEN cannot finalize with unresolved evidence",
                    default_used="unknown; no default",
                    affects=[identity + ":md", identity + ":json"],
                    status="open",
                    answer=None,
                )
                state.append(question)
                state.event("question", question.model_dump(mode="json"))
                for affected in question.affects:
                    state.edge(question.q_id, affected)
            for extension, path in paths.items():
                d = Deliverable(
                    d_id=identity + ":" + extension,
                    deal_ids=[registry.context.deal_id],
                    kind=DeliverableKind.SCREEN,
                    version=1,
                    status="draft",
                    path=str(path),
                    gate_results=[],
                    depends_on=dependencies,
                )
                state.append(d)
                for dep in dependencies:
                    state.edge(dep, d.d_id)
                references = {
                    k: evidence(request.headlines[k], facts[k])
                    for k in ("price", "units", "dscr", "market_tier")
                    if k in facts
                }
                plan = GatePlan(
                    citations=citations,
                    memo_pair=pair,
                    coverage=tuple(
                        CoverageField(
                            name=k,
                            doc_id=facts[k].provenance[0].doc_id,
                            references=(evidence(request.headlines[k], facts[k]),),
                        )
                        for k in REQUIRED
                    )
                    if not questions
                    else (),
                    buy_box=RuleCheck(references=references),
                    buy_box_policy=self.buy_box,
                )
                self.authority.put_plan(registry.context.scope, d, plan)
                other = "json" if extension == "md" else "md"
                self.inputs.register(
                    registry.context,
                    Artifact(
                        deliverable=d,
                        sha256=files.digest(bodies[extension]),
                        companions=(
                            ArtifactCompanion(
                                path=paths[other], sha256=files.digest(bodies[other])
                            ),
                        ),
                    ),
                )
                ids.append(d.d_id)
        return ScreenRun(
            run_id=request.run_id,
            recommendation=recommendation,
            classifications=classifications,
            risk=risk,
            markdown=markdown,
            json_memo=json_memo,
            deliverable_ids=tuple(ids),
            questions=tuple(dict.fromkeys(questions)),
            elapsed_ns=0,
        )

    def _render(
        self,
        facts: dict[str, Fact],
        refs: dict[str, Reference],
        classes: tuple[Classification, ...],
        recommendation: str,
        risk: CalcResult | None,
        questions: list[str],
    ) -> tuple[str, tuple[NumberCitation, ...]]:
        text = "# Screen memo\n\nRecommendation: " + recommendation + "\n\n## Headline facts\n"
        citations: list[NumberCitation] = []

        def append(line: str, ref: EvidenceRef | None = None) -> None:
            nonlocal text
            for token in extract_numbers(line):
                if ref is None:
                    raise Refusal("invalid_input", "Unexpected numerical memo token.")
                citations.append(
                    NumberCitation(
                        start=len(text) + token.start, end=len(text) + token.end, reference=ref
                    )
                )
            text += line

        for key in UNITS:
            label = key.replace("_", " ")
            fact = facts.get(key)
            if fact is None:
                append(label + ": unknown\n")
                continue
            claim = (
                "Seller assertion"
                if fact.claim_type == ClaimType.SELLER_ASSERTION
                else "Verified fact"
            )
            ref = evidence(refs[key], fact)
            value = format(fact.value, "f") if isinstance(fact.value, Decimal) else str(fact.value)
            period = " period " + ref.period if ref.period else ""
            display = f"{value} {fact.unit}" if "/" in str(fact.unit) else f"{fact.unit} {value}"
            append(f"{claim}: {label} {display}{period}\n", ref)
        append("\n## Risk\n")
        if risk is None:
            append("risk score: unknown\n")
        else:
            ref = EvidenceRef(
                kind="calc",
                record_id=risk.calc_id,
                deal_id=self.registry.context.deal_id,
                key="risk_score",
                unit="ratio",
                function="risk_score",
            )
            append("risk score ratio " + format(risk.outputs["risk_score"], "f") + "\n", ref)
        append(
            "Uncalibrated threshold breach index under host policy; "
            "seller inputs remain unverified.\n"
        )
        append("\n## Documents\n")
        for classification in classes:
            append(
                classification.kind.replace("t12", "trailing twelve").replace("_", " ")
                + " (rules)\n"
            )
        append("\n## Uncertainty\n")
        append(
            "Eligibility reflects policy only; independent source verification remains required.\n"
        )
        for question in dict.fromkeys(questions):
            append(question + ": unknown\n")
        return text, tuple(citations)
