"""Review regressions: local canonical evidence only; cached Excel is plumbing."""

from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from tests.gates.test_t037_workbook import workbook_env as original_workbook_env

from cre_brain.domain import CalcResult, DeliverableKind, Fact
from cre_brain.finance.returns import ReturnsInput, calculate_returns
from cre_brain.gates import EvidenceRef, GatePlan, NumberCitation, ReturnCheck, extract_numbers
from cre_brain.state.store import SqlVersionedStore


def cite(env, text, refs=None, **kwargs):
    service, inputs, _, scope, d, path, _ = env
    path.write_text(text)
    price = EvidenceRef(kind="fact", record_id="price", deal_id="deal", key="price", unit="USD")
    try:
        tokens = extract_numbers(text)
    except ValueError:
        tokens = ()
    refs = refs or [price] * len(tokens)
    inputs.put_plan(
        scope,
        d,
        GatePlan(
            citations=tuple(
                NumberCitation(start=n.start, end=n.end, reference=r)
                for n, r in zip(tokens, refs, strict=True)
            ),
            **kwargs,
        ),
    )
    return service


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", DeliverableKind.ESCALATION),
        ("status", "conditional"),
        ("path", "/tmp/unissued.md"),
        ("depends_on", []),
        ("deal_ids", ["other"]),
    ],
)
def test_t037_ac3_canonical_metadata_cannot_be_changed(gate_env, field, value):
    service = cite(gate_env, "price $100.", required_sections=("Risks",))
    changed = gate_env[4].model_copy(update={field: value})
    assert not service.check_all(changed).passed
    assert not service.check("number_provenance", changed).passed


@pytest.mark.parametrize("text", ["price -**$100**", "price (**$100**)"])
def test_t037_ac2_formatted_negative_currency_whole_gate(gate_env, text):
    # Existing lexer can produce a positive token; patched lexer may fail closed.
    service, inputs, _, scope, d, path, _ = gate_env
    path.write_text(text)
    try:
        tokens = extract_numbers(text)
    except ValueError:
        tokens = ()
    ref = EvidenceRef(kind="fact", record_id="price", deal_id="deal", key="price", unit="USD")
    inputs.put_plan(
        scope,
        d,
        GatePlan(
            citations=tuple(NumberCitation(start=n.start, end=n.end, reference=ref) for n in tokens)
        ),
    )
    assert not service.check("number_provenance", d).passed


@pytest.mark.parametrize("sign", ["-", "−"])
def test_t037_ac2_whitespace_cannot_detach_formatted_currency_sign(gate_env, sign):
    service = cite(gate_env, f"price {sign} **$100**")
    assert not service.check("number_provenance", gate_env[4]).passed


@pytest.mark.parametrize(
    "text",
    [
        "price - **USD 100**",
        "price -\u00a0**$100**",
        "price - <strong>$100</strong>",
        "price - [$100](#)",
    ],
)
def test_t037_ac2_codes_unicode_spacing_and_html_cannot_detach_currency_sign(gate_env, text):
    service = cite(gate_env, text)
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac2_thousand_header_cannot_cite_hundred_dollars(gate_env):
    service = cite(gate_env, "| Price ($000) |\n|---|\n|100|\n")
    assert not service.check("number_provenance", gate_env[4]).passed


@pytest.mark.parametrize("scale", ["thousand", "million"])
def test_t037_ac2_cell_scale_cannot_be_erased_by_currency_header(gate_env, scale):
    service = cite(gate_env, f"| Price ($) |\n|---|\n|100 {scale}|\n")
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac2_sentence_local_metric_binding(gate_env):
    service = cite(gate_env, "price $100. occupancy 100.")
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac2_currency_requires_a_display_dimension(gate_env):
    service = cite(gate_env, "price 100.")
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac2_comment_only_section_is_not_visible(gate_env):
    service = cite(gate_env, "# Risks\n<!-- pending -->", required_sections=("Risks",))
    assert not service.check("required_sections", gate_env[4]).passed


def returns_row(env, flows=("-100", "110"), identity="returns", issue=False):
    _, inputs, engine, scope, *_ = env
    source = ReturnsInput(
        input_id="flows",
        cash_flows=tuple(Decimal(v) for v in flows),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".05"),
    )
    inputs.put_input(scope, "deal", source)
    calc = calculate_returns(source, calc_id=identity, code_version="local-finance")
    if issue:
        from cre_brain.gates.models import FinanceRecipe

        inputs.put_recipe(
            scope,
            "deal",
            FinanceRecipe(
                calc_id=identity,
                function="calculate_returns",
                code_version="local-finance",
                source=source,
            ),
        )
    return calc, source


@pytest.mark.parametrize("fault", ["missing_recipe", "fake_output", "code_version", "disconnected"])
def test_t037_ac2_returns_require_reproducible_host_recipe(gate_env, fault):
    calc, _ = returns_row(gate_env, issue=fault != "missing_recipe")
    if fault == "fake_output":
        calc = calc.model_copy(update={"outputs": {**calc.outputs, "irr": Decimal(".50")}})
    elif fault == "code_version":
        calc = calc.model_copy(update={"code_version": "unapproved"})
    elif fault == "disconnected":
        calc = calc.model_copy(update={"inputs": {"cash_flows": "price"}})
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="irr",
        unit="ratio",
        function="calculate_returns",
    )
    service = cite(gate_env, f"irr {calc.outputs['irr'] * 100}%", [ref])
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac2_genuine_returns_recipe_recomputes_independent_of_context(gate_env):
    calc, _ = returns_row(gate_env, issue=True)
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="irr",
        unit="ratio",
        function="calculate_returns",
    )
    service = cite(gate_env, "irr 10%", [ref])
    with localcontext() as ctx:
        ctx.prec = 1
        assert service.check("number_provenance", gate_env[4]).passed


def test_t037_ac1_multiple_roots_require_visible_canonical_disclosure(gate_env):
    calc, source = returns_row(gate_env, flows=("-100", "230", "-132"), issue=True)
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="reported_return",
        unit="ratio",
        function="calculate_returns",
    )
    service = cite(
        gate_env,
        "reported return only.",
        returns=(ReturnCheck(reference=ref, input_id=source.input_id),),
    )
    assert not service.check("irr_sanity", gate_env[4]).passed


def test_t037_ac2_decimal_budget_precedes_fraction(gate_env):
    service, _, engine, scope, d, _, fact = gate_env
    SqlVersionedStore(engine, Fact).append(
        fact.model_copy(update={"version": 2, "value": Decimal("1e1000000")}), scope=scope
    )
    ref = EvidenceRef(
        kind="fact", record_id="price", deal_id="deal", key="price", unit="USD", version=2
    )
    cite(gate_env, "price $100", [ref])
    result = service.check("number_provenance", d)
    assert not result.passed
    assert result.failures == ["number_provenance: resource_limit"]


def test_t037_ac1_backend_errors_are_sanitized(gate_env):
    class Broken:
        def plan(self, *args):
            raise RuntimeError("SECRET source /private/raw-owner-name")

    gate_env[0].inputs = Broken()
    result = gate_env[0].check("number_provenance", gate_env[4])
    assert result.failures == ["number_provenance: authority_unavailable"]


@pytest.mark.parametrize("fault", ["ratio", "no_source", "date", "format"])
def test_t037_ac2_workbook_semantic_provenance(workbook_env, fault):
    import xml.etree.ElementTree as ET
    import zipfile

    service, d, output, files = workbook_env
    # Mutate OOXML directly to retain the synthetic cached formula controls.
    root = ET.fromstring(files["xl/worksheets/sheet1.xml"])
    if fault == "ratio":
        root.find(".//{*}c[@r='B4']/{*}v").text = ".53"
    elif fault == "date":
        row = ET.SubElement(
            root.find("{*}sheetData"),
            "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row",
            {"r": "20"},
        )
        cell = ET.SubElement(
            row,
            "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c",
            {"r": "B20", "t": "d"},
        )
        ET.SubElement(
            cell, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
        ).text = "2026-10-04T00:00:00"
    elif fault == "format":
        styles = ET.fromstring(files["xl/styles.xml"])
        styles.find("{*}numFmts/{*}numFmt").set("formatCode", '"100%"')
        files["xl/styles.xml"] = ET.tostring(styles)
    else:
        facts = SqlVersionedStore(service.engine, Fact)
        fact = facts.get("annual_revenue_growth", scope=service.scope)
        facts.append(fact.model_copy(update={"version": 2, "provenance": []}), scope=service.scope)
    files["xl/worksheets/sheet1.xml"] = ET.tostring(root)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    assert not service.check("number_provenance", d).passed


def test_t037_ac2_text_size_is_bounded_before_read(gate_env):
    service, _, _, _, d, path, _ = gate_env
    cite(gate_env, "No numbers")
    with path.open("wb") as stream:
        stream.truncate(8 * 1024 * 1024 + 1)
    assert service.check("number_provenance", d).failures == ["number_provenance: resource_limit"]


@pytest.mark.parametrize("fault", ["other_deal", "other_period", "ambiguous_metric"])
def test_t037_ac2_occurrence_scope_is_local(gate_env, fault):
    service, inputs, engine, scope, d, path, fact = gate_env
    if fault == "other_deal":
        d = d.model_copy(update={"deal_ids": ["deal", "other"]})
        text = "other price $100. deal price $100."
    elif fault == "other_period":
        from cre_brain.domain import DateRange

        SqlVersionedStore(engine, Fact).append(
            fact.model_copy(
                update={
                    "version": 2,
                    "valid_time": DateRange(
                        start=datetime(2026, 10, 1).date(), end=datetime(2026, 10, 4).date()
                    ),
                }
            ),
            scope=scope,
        )
        text = "price $100 for prior period."
    else:
        text = "price occupancy $100."
    path.write_text(text)
    ref = EvidenceRef(
        kind="fact",
        record_id="price",
        deal_id="deal",
        key="price",
        unit="USD",
        version=2 if fault == "other_period" else 1,
    )
    inputs.put_plan(
        scope,
        d,
        GatePlan(
            citations=tuple(
                NumberCitation(start=n.start, end=n.end, reference=ref)
                for n in extract_numbers(text)
            )
        ),
    )
    assert not service.check("number_provenance", d).passed


@pytest.fixture
def model_env(gate_env):
    """Real finance inputs/results, host recipes, complete assumption inventory."""
    from hashlib import sha256

    from cre_brain.domain import Assumption, ClaimType, Provenance
    from cre_brain.finance.proforma import ProFormaInput, build_proforma
    from cre_brain.gates.models import AssumptionCheck, FinanceRecipe, ModelContract

    service, inputs, engine, scope, d, path, _ = gate_env
    values = dict(
        base_monthly_revenue=Decimal(100),
        base_monthly_operating_expenses=Decimal(40),
        annual_revenue_growth=Decimal(".03"),
        annual_expense_growth=Decimal(".02"),
        vacancy_rate=Decimal(".05"),
        credit_loss_rate=Decimal(".01"),
        monthly_reserves=Decimal(2),
    )
    facts = SqlVersionedStore(engine, Fact)
    assumptions = SqlVersionedStore(engine, Assumption)
    refs, checks = {}, {}
    for key, value in values.items():
        unit = "ratio" if "rate" in key or "growth" in key else "USD/month"
        facts.append(
            Fact(
                fact_id=key,
                deal_id="deal",
                key=key,
                value=value,
                unit=unit,
                claim_type=ClaimType.VERIFIED_FACT,
                provenance=[Provenance(doc_id="source", page=1)],
                known_at=datetime(2026, 10, 1, tzinfo=UTC),
                version=1,
            ),
            scope=scope,
        )
        refs[key] = EvidenceRef(kind="fact", record_id=key, deal_id="deal", key=key, unit=unit)
        assumptions.append(
            Assumption(
                key=key,
                value=value,
                low=Decimal(0),
                high=Decimal(200),
                sources=[key],
                rationale="Dated host policy",
                is_proxy=False,
                as_of=service.state.as_of,
                set_by="firm_policy",
            ),
            scope=scope,
            record_id="assumption-" + key,
        )
        checks[key] = AssumptionCheck(record_id="assumption-" + key, deal_id="deal", unit=unit)
    facts.append(
        Fact(
            fact_id="projection_months",
            deal_id="deal",
            key="projection_months",
            value=Decimal(60),
            unit="count",
            claim_type=ClaimType.VERIFIED_FACT,
            provenance=[Provenance(doc_id="policy", page=1)],
            known_at=datetime(2026, 10, 1, tzinfo=UTC),
            version=1,
        ),
        scope=scope,
    )
    assumptions.append(
        Assumption(
            key="projection_months",
            value=Decimal(60),
            low=Decimal(60),
            high=Decimal(60),
            rationale="Host template horizon",
            sources=["projection_months"],
            is_proxy=False,
            as_of=service.state.as_of,
            set_by="firm_policy",
        ),
        scope=scope,
        record_id="assumption-projection_months",
    )
    checks["projection_months"] = AssumptionCheck(
        record_id="assumption-projection_months", deal_id="deal", unit="count"
    )
    source = ProFormaInput(input_id="model-input", projection_months=60, **values)
    recipe = FinanceRecipe(
        calc_id="model",
        function="build_proforma",
        code_version="local-finance",
        source=source,
        dependencies=refs,
        model_id="underwriting",
        model_version=1,
        scenario_parameters={"rent_growth": "annual_revenue_growth"},
    )
    inputs.put_recipe(scope, "deal", recipe)
    calc = build_proforma(source, calc_id="model", code_version="local-finance").model_copy(
        update={"inputs": {k: r.record_id for k, r in refs.items()}}
    )
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    artifact = path.parent / "model.json"
    artifact.write_text(calc.model_dump_json())
    model = ModelContract(
        calc_id="model",
        deal_id="deal",
        code_version="local-finance",
        model_id="underwriting",
        model_version=1,
        artifact=artifact,
        sha256=sha256(artifact.read_bytes()).hexdigest(),
        assumptions=checks,
    )
    for key, value, unit in (
        ("market_tier", "A", "text"),
        ("asset_class", "A", "text"),
        ("vintage", Decimal(2000), "year"),
        ("rent_growth", Decimal(".03"), "ratio"),
        ("cap_rate", Decimal(".05"), "ratio"),
    ):
        facts.append(
            Fact(
                fact_id=key,
                deal_id="deal",
                key=key,
                value=value,
                unit=unit,
                claim_type=ClaimType.VERIFIED_FACT,
                provenance=[Provenance(doc_id="policy", page=1)],
                known_at=datetime(2026, 10, 1, tzinfo=UTC),
                version=1,
            ),
            scope=scope,
        )
        refs[key] = EvidenceRef(kind="fact", record_id=key, deal_id="deal", key=key, unit=unit)
    return gate_env, recipe, model, refs, checks


@pytest.mark.parametrize("fault", ["empty", "incomplete", "disconnected", "proxy"])
def test_t037_ac1_actual_assumption_inventory_is_exhaustive(model_env, fault):
    from cre_brain.domain import Assumption
    from cre_brain.gates.models import RuleCheck

    env, recipe, model, refs, checks = model_env
    service, inputs, engine, scope, d, _, _ = env
    # A disconnected compliant rule source must not authorize model inputs.
    rules = RuleCheck(
        references={
            key: refs[key]
            for key in ("market_tier", "asset_class", "vintage", "rent_growth", "cap_rate")
        }
    )
    inventory = tuple(checks.values())
    if fault == "empty":
        inventory = ()
    elif fault == "incomplete":
        inventory = inventory[:-1]
    elif fault == "disconnected":
        model = model.model_copy(
            update={"assumptions": {**checks, "annual_revenue_growth": checks["vacancy_rate"]}}
        )
    else:
        store = SqlVersionedStore(engine, Assumption)
        record = store.get(checks["annual_revenue_growth"].record_id, scope=scope)
        store.append(
            record.model_copy(update={"is_proxy": True}),
            scope=scope,
            record_id=checks["annual_revenue_growth"].record_id,
        )
        checks["annual_revenue_growth"] = checks["annual_revenue_growth"].model_copy(
            update={"version": 2}
        )
        inventory = tuple(checks.values())
        model = model.model_copy(update={"assumptions": checks})
    inputs.put_plan(scope, d, GatePlan(model=model, assumptions=inventory, assumption_ranges=rules))
    assert not service.check("assumption_ranges", d).passed


def test_t037_ac2_fact_dependency_version_is_pinned_without_stale_event(model_env):
    env, _, model, refs, _ = model_env
    fact_store = SqlVersionedStore(env[2], Fact)
    fact = fact_store.get("annual_revenue_growth", scope=env[3])
    fact_store.append(fact.model_copy(update={"version": 2, "value": Decimal(".50")}), scope=env[3])
    ref = EvidenceRef(
        kind="calc",
        record_id="model",
        deal_id="deal",
        key="year:2:noi",
        unit="USD",
        function="build_proforma",
    )
    service = cite(env, "noi $100", [ref], model=model)
    assert not service.check("number_provenance", env[4]).passed


def test_t037_ac1_fragility_cannot_swap_assumptions_for_genuine_result(model_env):
    from cre_brain.finance.proforma import build_proforma
    from cre_brain.finance.scenarios import AssumptionRange, FragilityInput
    from cre_brain.gates.models import FragilityCheck, ScenarioCheck

    env, recipe, model, refs, _ = model_env
    service, inputs, engine, scope, d, *_ = env
    source = recipe.source.model_copy(
        update={"input_id": "down-input", "annual_revenue_growth": Decimal(".01")}
    )
    down_recipe = recipe.model_copy(
        update={"calc_id": "down", "source": source, "dependencies": {}}
    )
    inputs.put_recipe(scope, "deal", down_recipe)
    calc = build_proforma(source, calc_id="down", code_version=recipe.code_version)
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    policy = FragilityInput(
        input_id="fragility",
        ranges=(
            AssumptionRange(
                input_id="range",
                name="rent_growth",
                p10=Decimal(".01"),
                base=Decimal(".03"),
                p90=Decimal(".05"),
                downside="decrease",
            ),
        ),
        metric_key="year:2:noi",
        target=Decimal(665),
        fragility_margin=service.settings.fragility_margin,
    )
    inputs.put_input(scope, "deal", policy)
    base_ref = EvidenceRef(
        kind="calc",
        record_id="model",
        deal_id="deal",
        key=policy.metric_key,
        unit="USD",
        function="build_proforma",
    )
    check = FragilityCheck(
        input_id="fragility",
        deal_id="deal",
        base=base_ref,
        scenarios=(
            ScenarioCheck(
                input_id="down-input",
                result=base_ref.model_copy(update={"record_id": "down"}),
                assumptions={"rent_growth": refs["annual_revenue_growth"]},
            ),
        ),
    )
    inputs.put_plan(scope, d, GatePlan(model=model, fragility=check))
    assert not service.check("fragility", d).passed


@pytest.fixture
def workbook_env(gate_env):
    from cre_brain.finance.proforma import ProFormaInput
    from cre_brain.gates.models import FinanceRecipe

    result = original_workbook_env.__wrapped__(gate_env)
    service, d, _, _ = result
    plan = service.inputs.plan(service.scope, d)
    entries = [e for e in plan.workbook.mapping.entries if e.source == "fact"]
    refs = {
        e.key: EvidenceRef(kind="fact", record_id=e.key, deal_id="deal", key=e.key, unit=e.unit)
        for e in entries
    }
    values = {key: service.state.resolve(ref, d) for key, ref in refs.items()}
    service.inputs.put_recipe(
        service.scope,
        "deal",
        FinanceRecipe(
            calc_id="proforma",
            function="build_proforma",
            code_version="test",
            source=ProFormaInput(input_id="base_monthly_revenue", projection_months=60, **values),
            dependencies=refs,
        ),
    )
    assert service.check("number_provenance", d).passed
    return result


def test_t037_ac1_complete_model_assumptions_pass(model_env):
    from cre_brain.gates.models import RuleCheck

    env, _, model, refs, checks = model_env
    rules = RuleCheck(
        references={
            key: refs[key]
            for key in ("market_tier", "asset_class", "vintage", "rent_growth", "cap_rate")
        }
    )
    env[1].put_plan(
        env[3],
        env[4],
        GatePlan(model=model, assumptions=tuple(checks.values()), assumption_ranges=rules),
    )
    assert env[0].check("assumption_ranges", env[4]).passed


def test_t037_ac1_real_multiple_root_disclosure_passes_and_hidden_roots_fail(gate_env):
    calc, source = returns_row(gate_env, flows=("-100", "230", "-132"), issue=True)
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    refs, lines, labels = [], ["Multiple IRR roots; MIRR fallback is reported."], {}
    for key in ("root_count", "root:0", "root:1", "mirr"):
        label = (
            "IRR root count"
            if key == "root_count"
            else "IRR root"
            if key.startswith("root:")
            else "MIRR fallback"
        )
        label_unit = "count" if key == "root_count" else "ratio"
        display = (
            str(calc.outputs[key]) if key == "root_count" else str(calc.outputs[key] * 100) + "%"
        )
        lines.append(f"{label} {display}.")
        labels[key] = (label,)
        refs.append(
            EvidenceRef(
                kind="calc",
                record_id="returns",
                deal_id="deal",
                key=key,
                unit=label_unit,
                function="calculate_returns",
            )
        )
    ref = refs[-1].model_copy(update={"key": "reported_return"})
    check = ReturnCheck(reference=ref, input_id=source.input_id)
    service = cite(gate_env, "\n".join(lines), refs, labels=labels, returns=(check,))
    assert service.check("irr_sanity", gate_env[4]).passed
    hidden = "\n".join(
        lines[:2] + ["<!-- " + lines[2] + " -->", "<!-- " + lines[3] + " -->"] + lines[4:]
    )
    cite(gate_env, hidden, refs, labels=labels, returns=(check,))
    assert not service.check("irr_sanity", gate_env[4]).passed


def test_t037_ac1_growth_evidence_cannot_replace_actual_fifty_percent_input(model_env):
    from hashlib import sha256

    from cre_brain.domain import Assumption
    from cre_brain.finance.proforma import build_proforma
    from cre_brain.gates.models import RuleCheck

    env, recipe, model, refs, checks = model_env
    source = recipe.source.model_copy(
        update={"input_id": "high-growth", "annual_revenue_growth": Decimal(".50")}
    )
    new_recipe = recipe.model_copy(
        update={"calc_id": "high-model", "source": source, "dependencies": {}}
    )
    env[1].put_recipe(env[3], "deal", new_recipe)
    calc = build_proforma(source, calc_id="high-model", code_version=recipe.code_version)
    SqlVersionedStore(env[2], CalcResult).append(calc, scope=env[3])
    facts = SqlVersionedStore(env[2], Fact)
    fact = facts.get("annual_revenue_growth", scope=env[3])
    facts.append(fact.model_copy(update={"version": 2, "value": Decimal(".50")}), scope=env[3])
    store = SqlVersionedStore(env[2], Assumption)
    check = checks["annual_revenue_growth"]
    record = store.get(check.record_id, scope=env[3])
    store.append(
        record.model_copy(update={"value": Decimal(".50")}), scope=env[3], record_id=check.record_id
    )
    checks["annual_revenue_growth"] = check.model_copy(update={"version": 2})
    model.artifact.write_text(calc.model_dump_json())
    model = model.model_copy(
        update={
            "calc_id": "high-model",
            "sha256": sha256(model.artifact.read_bytes()).hexdigest(),
            "assumptions": checks,
        }
    )
    rules = RuleCheck(
        references={
            key: refs[key]
            for key in ("market_tier", "asset_class", "vintage", "rent_growth", "cap_rate")
        }
    )
    env[1].put_plan(
        env[3],
        env[4],
        GatePlan(model=model, assumptions=tuple(checks.values()), assumption_ranges=rules),
    )
    assert not env[0].check("assumption_ranges", env[4]).passed


def test_t037_ac2_model_artifact_and_recipe_are_both_required(model_env):
    env, _, model, _, _ = model_env
    ref = EvidenceRef(
        kind="calc",
        record_id="model",
        deal_id="deal",
        key="year:2:noi",
        unit="USD",
        function="build_proforma",
        period="year 2",
    )
    # A host binds this actual model; unrelated/fact-only references cannot stand in.
    service = cite(env, "No numeric claims", model=model, model_bindings={ref.key: ref})
    assert service.check("numbers_match_model", env[4]).passed
    model.artifact.write_text("changed model")
    assert not service.check("numbers_match_model", env[4]).passed


@pytest.mark.parametrize("fault", ["hidden_zero", "hidden_negative", "count_slack"])
def test_t037_ac2_workbook_formats_cannot_hide_numeric_semantics(workbook_env, fault):
    import xml.etree.ElementTree as ET
    import zipfile

    service, d, output, files = workbook_env
    styles = ET.fromstring(files["xl/styles.xml"])
    fmt = {
        "hidden_zero": '0.000000;;"profit"',
        "hidden_negative": "0.000000;0.000000",
        "count_slack": "0%",
    }[fault]
    styles.find("{*}numFmts/{*}numFmt").set("formatCode", fmt)
    files["xl/styles.xml"] = ET.tostring(styles)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    assert not service.check("number_provenance", d).passed


def test_t037_ac2_zip_budget_precedes_workbook_reader(gate_env, monkeypatch):
    import zipfile

    service, inputs, _, scope, d, path, _ = gate_env
    output = path.with_suffix(".xlsx")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb.xml", b"0" * (32 * 1024 * 1024 + 1))
    d = d.model_copy(update={"path": str(output)})
    inputs.put_plan(scope, d, GatePlan())

    def forbidden_reader(*args, **kwargs):
        raise AssertionError("Workbook reader ran before package budget")

    monkeypatch.setattr("cre_brain.gates.service.load_workbook", forbidden_reader)
    assert service.check("number_provenance", d).failures == ["number_provenance: resource_limit"]


def test_t037_ac2_ic_return_provenance_cannot_hide_multiple_roots(gate_env):
    calc, _ = returns_row(gate_env, flows=("-100", "230", "-132"), issue=True)
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="reported_return",
        unit="ratio",
        function="calculate_returns",
    )
    service = cite(gate_env, f"reported return {calc.outputs['reported_return'] * 100}%", [ref])
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac2_fixed_excel_format_cannot_round_nonzero_to_zero(gate_env):
    from cre_brain.gates.presentation import displayed_decimal

    value = Decimal(".0000001")
    with localcontext() as context:
        context.prec = 1
        assert displayed_decimal(value, "0.000000", "ratio") == 0
        assert displayed_decimal(Decimal(".03"), "0.00%", "ratio") == Decimal(".03")
    store = SqlVersionedStore(gate_env[2], Fact)
    store.append(
        gate_env[6].model_copy(update={"version": 2, "value": Decimal(0)}), scope=gate_env[3]
    )
    ref = EvidenceRef(
        kind="fact", record_id="price", deal_id="deal", key="price", unit="USD", version=2
    )
    service = cite(gate_env, "price $0", [ref])
    assert service.check("number_provenance", gate_env[4]).passed
    cite(gate_env, "price -$0", [ref])
    assert not service.check("number_provenance", gate_env[4]).passed


def test_t037_ac1_negated_ambiguity_is_not_canonical_disclosure(gate_env):
    calc, source = returns_row(gate_env, flows=("-100", "230", "-132"), issue=True)
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    lines, refs, labels = ["No multiple IRR roots."], [], {}
    for key in ("root_count", "root:0", "root:1", "mirr"):
        label = (
            "root count"
            if key == "root_count"
            else "root"
            if key.startswith("root:")
            else "MIRR fallback"
        )
        value = (
            str(calc.outputs[key]) if key == "root_count" else str(calc.outputs[key] * 100) + "%"
        )
        lines.append(f"{label} {value}.")
        labels[key] = (label,)
        refs.append(
            EvidenceRef(
                kind="calc",
                record_id="returns",
                deal_id="deal",
                key=key,
                unit="count" if key == "root_count" else "ratio",
                function="calculate_returns",
            )
        )
    check = ReturnCheck(reference=refs[-1], input_id=source.input_id)
    service = cite(gate_env, "\n".join(lines), refs, labels=labels, returns=(check,))
    assert not service.check("irr_sanity", gate_env[4]).passed


@pytest.mark.parametrize(
    "classification,prefix,suffix",
    [
        ("Multiple IRR roots: absent.", "No ", ""),
        ("Multiple IRR roots.", "", " is not used"),
        ("Multiple IRR roots.", "No\n", ""),
        ("Multiple IRR roots.", "Ignore ", ""),
        ("Multiple IRR roots.", "", " is never used"),
    ],
)
def test_t037_ac1_negated_root_and_mirr_clauses_cannot_satisfy_disclosure(
    gate_env, classification, prefix, suffix
):
    calc, source = returns_row(gate_env, flows=("-100", "230", "-132"), issue=True)
    SqlVersionedStore(gate_env[2], CalcResult).append(calc, scope=gate_env[3])
    lines = [classification]
    refs, labels = [], {}
    for key in ("root_count", "root:0", "root:1", "mirr"):
        label = (
            "root count"
            if key == "root_count"
            else "root"
            if key.startswith("root:")
            else "MIRR fallback"
        )
        value = (
            str(calc.outputs[key]) if key == "root_count" else str(calc.outputs[key] * 100) + "%"
        )
        leading, trailing = (prefix, suffix) if key == "mirr" else ("", "")
        lines.append(f"{leading}{label} {value}{trailing}.")
        labels[key] = (label,)
        refs.append(
            EvidenceRef(
                kind="calc",
                record_id="returns",
                deal_id="deal",
                key=key,
                unit="count" if key == "root_count" else "ratio",
                function="calculate_returns",
            )
        )
    service = cite(
        gate_env,
        "\n".join(lines),
        refs,
        labels=labels,
        returns=(ReturnCheck(reference=refs[-1], input_id=source.input_id),),
    )
    assert not service.check("irr_sanity", gate_env[4]).passed


@pytest.mark.parametrize("hidden", [False, True])
def test_t037_ac2_issued_workbook_unmapped_number_is_still_rejected(workbook_env, hidden):
    import xml.etree.ElementTree as ET
    import zipfile

    service, d, output, files = workbook_env
    root = ET.fromstring(files["xl/worksheets/sheet1.xml"])
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    row = ET.SubElement(
        root.find("{*}sheetData"),
        namespace + "row",
        {"r": "20", **({"hidden": "1"} if hidden else {})},
    )
    cell = ET.SubElement(row, namespace + "c", {"r": "B20", "t": "n"})
    ET.SubElement(cell, namespace + "v").text = "777"
    files["xl/worksheets/sheet1.xml"] = ET.tostring(root)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    assert not service.check("number_provenance", d).passed
