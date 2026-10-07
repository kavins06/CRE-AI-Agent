"""Synthetic deterministic gate contracts; no models, live services or eval data."""

from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from sqlalchemy import create_engine

from cre_brain.config.settings import GateSettings
from cre_brain.domain import CalcResult, ClaimType, Deliverable, DeliverableKind, Fact, Provenance
from cre_brain.domain.base import TenantScope
from cre_brain.finance.returns import ReturnsInput, calculate_returns
from cre_brain.gates import (
    CATALOG,
    REGISTRY,
    Checksum,
    CoverageField,
    EvidenceRef,
    GatePlan,
    GateService,
    NumberCitation,
    ReturnCheck,
    RuleCheck,
    TrustedInputs,
    extract_numbers,
)
from cre_brain.state.graph import DependencyGraph
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore


@pytest.fixture
def env(tmp_path):
    from datetime import date

    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    scope = TenantScope(user_id="user", firm_id="firm")
    settings = GateSettings(
        parity_abs="1",
        parity_rel="0.000001",
        checksum_abs="1",
        number_abs="1",
        number_rel="0.000001",
        fragility_margin="0.02",
        excel_functions=("SUM", "IF", "MAX"),
    )
    inputs = TrustedInputs()
    service = GateService(
        engine,
        scope=scope,
        settings=settings,
        inputs=inputs,
        scratch=tmp_path / "scratch",
        as_of=date(2026, 10, 4),
    )
    path = tmp_path / "memo.md"
    path.write_text("price $100\n", encoding="utf-8")
    d = Deliverable(
        d_id="deliverable",
        deal_ids=["deal"],
        kind=DeliverableKind.IC_MEMO,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=["price"],
    )

    def add(key, value, unit="USD", **kw):
        existing = SqlVersionedStore(engine, Fact).get(kw.get("fact_id", key), scope=scope)
        if existing is not None and not kw and existing.value == value and existing.unit == unit:
            return EvidenceRef(
                kind="fact",
                record_id=existing.fact_id,
                deal_id=existing.deal_id,
                version=existing.version,
                key=existing.key,
                unit=unit,
            )
        f = Fact(
            fact_id=kw.pop("fact_id", key),
            deal_id=kw.pop("deal_id", "deal"),
            key=key,
            value=value,
            unit=unit,
            claim_type=ClaimType.VERIFIED_FACT,
            provenance=[Provenance(doc_id="document", page=1)],
            known_at=datetime(2026, 10, 1, tzinfo=UTC),
            version=kw.pop("version", 1),
            **kw,
        )
        SqlVersionedStore(engine, Fact).append(f, scope=scope)
        return EvidenceRef(
            kind="fact",
            record_id=f.fact_id,
            deal_id=f.deal_id,
            version=f.version,
            key=f.key,
            unit=unit,
        )

    price = add("price", Decimal(100))
    yield service, inputs, engine, scope, d, path, add, price
    engine.dispose()


def register(env, *, deliverable=None, **kw):
    service, inputs, _, scope, d, *_ = env
    inputs.put_plan(scope, deliverable or d, GatePlan(**kw))
    return service


def issue_returns(env, source, *, calc_id="returns", model_id=None):
    from cre_brain.gates.models import FinanceRecipe

    env[1].put_recipe(
        env[3],
        "deal",
        FinanceRecipe(
            calc_id=calc_id,
            function="calculate_returns",
            code_version="test",
            source=source,
            model_id=model_id,
            scenario_parameters={"reinvest_rate": "reinvest_rate"} if model_id else {},
        ),
    )


def model_contract(env, calc, *, model_id="model", assumptions=None):
    from hashlib import sha256

    from cre_brain.gates.models import ModelContract

    artifact = env[5].parent / (calc.calc_id + ".json")
    artifact.write_text(calc.model_dump_json())
    return ModelContract(
        calc_id=calc.calc_id,
        deal_id="deal",
        code_version=calc.code_version,
        model_id=model_id,
        model_version=1,
        artifact=artifact,
        sha256=sha256(artifact.read_bytes()).hexdigest(),
        assumptions=assumptions or {},
    )


def range_model(env, refs, existing=None):
    from cre_brain.domain import Assumption
    from cre_brain.finance.proforma import ProFormaInput, build_proforma
    from cre_brain.gates.models import AssumptionCheck, FinanceRecipe

    values = dict(
        base_monthly_revenue=Decimal(100),
        base_monthly_operating_expenses=Decimal(40),
        annual_revenue_growth=Decimal(".03"),
        annual_expense_growth=Decimal(".02"),
        vacancy_rate=Decimal(".05"),
        credit_loss_rate=Decimal(".01"),
        monthly_reserves=Decimal(2),
    )
    dependencies, checks = {}, {}
    store = SqlVersionedStore(env[2], Assumption)
    for key, value in values.items():
        unit = "ratio" if "rate" in key or "growth" in key else "USD/month"
        source_key = "rent_growth" if key == "annual_revenue_growth" else key
        dependencies[key] = (
            refs["rent_growth"] if source_key == "rent_growth" else env[6](key, value, unit)
        )
        if existing and key == "annual_revenue_growth":
            checks[key] = existing
            continue
        identity = "assumption-" + key
        store.append(
            Assumption(
                key=source_key,
                value=value,
                low=Decimal(0),
                high=Decimal(200),
                rationale="Canonical fixture policy",
                sources=[dependencies[key].record_id],
                is_proxy=False,
                as_of=env[0].state.as_of,
                set_by="firm_policy",
            ),
            scope=env[3],
            record_id=identity,
        )
        checks[key] = AssumptionCheck(record_id=identity, deal_id="deal", unit=unit)
    env[6]("projection_months", Decimal(60), "count")
    store.append(
        Assumption(
            key="projection_months",
            value=Decimal(60),
            low=Decimal(60),
            high=Decimal(60),
            rationale="Host template horizon",
            sources=["projection_months"],
            is_proxy=False,
            as_of=env[0].state.as_of,
            set_by="firm_policy",
        ),
        scope=env[3],
        record_id="assumption-projection_months",
    )
    checks["projection_months"] = AssumptionCheck(
        record_id="assumption-projection_months", deal_id="deal", unit="count"
    )
    source = ProFormaInput(input_id="operating-input", projection_months=60, **values)
    env[1].put_recipe(
        env[3],
        "deal",
        FinanceRecipe(
            calc_id="operating-model",
            function="build_proforma",
            code_version="test",
            source=source,
            dependencies=dependencies,
            model_id="model",
        ),
    )
    calc = build_proforma(source, calc_id="operating-model", code_version="test").model_copy(
        update={"inputs": {k: r.record_id for k, r in dependencies.items()}}
    )
    SqlVersionedStore(env[2], CalcResult).append(calc, scope=env[3])
    return model_contract(env, calc, assumptions=checks), tuple(checks.values())


@pytest.mark.parametrize(
    "gate",
    [
        "coverage",
        "checksums",
        "parity",
        "excel_errors",
        "assumption_ranges",
        "irr_sanity",
        "fragility",
        "buy_box",
        "number_provenance",
        "numbers_match_model",
        "required_sections",
        "policy_bands",
    ],
)
def test_t037_ac1_missing_required_inputs_never_silently_pass(env, gate):
    service = register(env)
    assert not service.check(gate, env[4]).passed


def test_t037_ac3_exact_catalog_and_advisory():
    assert CATALOG[DeliverableKind.SCREEN] == ("coverage", "buy_box", "number_provenance")
    assert CATALOG[DeliverableKind.UW_MODEL] == (
        "checksums",
        "parity",
        "excel_errors",
        "assumption_ranges",
        "irr_sanity",
        "fragility",
        "number_provenance",
    )
    assert CATALOG[DeliverableKind.IC_MEMO] == (
        "number_provenance",
        "numbers_match_model",
        "required_sections",
        "entailment",
    )
    assert CATALOG[DeliverableKind.LOI] == ("policy_bands", "number_provenance", "entailment")
    assert CATALOG[DeliverableKind.DD_TRACKER] == ("coverage", "number_provenance")
    assert set(CATALOG) == set(DeliverableKind)
    for kind in set(DeliverableKind) - {
        DeliverableKind.SCREEN,
        DeliverableKind.UW_MODEL,
        DeliverableKind.IC_MEMO,
        DeliverableKind.LOI,
        DeliverableKind.DD_TRACKER,
    }:
        assert CATALOG[kind] == ("number_provenance",)
    assert set(REGISTRY) == {
        "coverage",
        "checksums",
        "parity",
        "excel_errors",
        "assumption_ranges",
        "irr_sanity",
        "fragility",
        "buy_box",
        "number_provenance",
        "numbers_match_model",
        "required_sections",
        "policy_bands",
        "entailment",
        "verifier",
    }
    assert not REGISTRY["entailment"].blocking and not REGISTRY["verifier"].blocking


def test_t037_ac4_coverage_pass_and_planted_missing_document(env):
    field = CoverageField(name="price", doc_id="document", references=(env[7],))
    service = register(env, coverage=(field,))
    assert service.check("coverage", env[4]).passed
    field = field.model_copy(update={"doc_id": "unrelated"})
    register(env, coverage=(field,))
    assert not service.check("coverage", env[4]).passed


def test_t037_ac4_checksum_pass_and_planted_count_difference(env):
    add = env[6]
    one, two, total = (
        add("one", Decimal(2), "count"),
        add("two", Decimal(3), "count"),
        add("total", Decimal(5), "count"),
    )
    check = Checksum(name="units", parts=(one, two), total=total, unit="count")
    service = register(env, checksums=(check,))
    with localcontext() as ctx:
        ctx.prec = 1
        assert service.check("checksums", env[4]).passed
    wrong = add("wrong", Decimal("5.5"), "count")
    register(env, checksums=(check.model_copy(update={"total": wrong}),))
    assert not service.check("checksums", env[4]).passed


def test_t037_ac4_number_provenance_pass_and_planted_unrelated_forgery(env):
    service, _, _, _, d, path, add, price = env
    token = extract_numbers(path.read_text())[0]
    citation = NumberCitation(start=token.start, end=token.end, reference=price)
    register(env, citations=(citation,))
    assert service.check("number_provenance", d).passed
    other = add("unrelated", Decimal(100))
    register(env, citations=(citation.model_copy(update={"reference": other}),))
    assert not service.check("number_provenance", d).passed
    register(env, citations=(citation,))
    path.write_text("price $100\n> `secret 777`\n", encoding="utf-8")
    assert not service.check("number_provenance", d).passed


@pytest.mark.parametrize(
    "attack",
    [
        "tenant",
        "deal",
        "stale",
        "version",
        "conflict",
        "claim_text",
        "unit",
        "nonfinite",
        "pass_object",
    ],
)
def test_t037_ac2_canonical_identity_fail_closed(env, attack):
    service, inputs, engine, scope, d, path, add, price = env
    token = extract_numbers(path.read_text())[0]
    if attack == "tenant":
        service = GateService(
            engine,
            scope=TenantScope(user_id="other", firm_id="firm"),
            settings=service.settings,
            inputs=inputs,
            scratch=path.parent / "other",
        )
    elif attack == "deal":
        price = add("price", Decimal(100), fact_id="other-price", deal_id="other")
    elif attack == "stale":
        graph = DependencyGraph(engine, release_id="gates")
        graph.add_edge("changed", "price", scope=scope)
        graph.mark_stale("changed", task_id="task", scope=scope)
    elif attack == "version":
        add("price", Decimal(200), version=2)
    elif attack == "conflict":
        f = SqlVersionedStore(engine, Fact).get("price", scope=scope)
        SqlVersionedStore(engine, Fact).append(
            f.model_copy(update={"version": 2, "claim_type": ClaimType.CONFLICT}), scope=scope
        )
        price = price.model_copy(update={"version": 2})
    elif attack == "claim_text":
        price = add("claim", "price $100", unit="USD")
    elif attack == "unit":
        price = price.model_copy(update={"unit": "EUR"})
    elif attack == "nonfinite":
        with pytest.raises(ValueError):
            add("bad", Decimal("NaN"))
        return
    elif attack == "pass_object":
        from cre_brain.domain import GateResult

        d = d.model_copy(
            update={"gate_results": [GateResult(passed=True, failures=[], metrics={})]}
        )
        price = price.model_copy(update={"record_id": "missing"})
    register(env, citations=(NumberCitation(start=token.start, end=token.end, reference=price),))
    assert not service.check("number_provenance", d).passed


def rule_refs(env, values):
    return {key: env[6](key, value, unit) for key, (value, unit) in values.items()}


def test_t037_ac4_buy_box_pass_and_planted_failure(env):
    refs = rule_refs(
        env,
        {
            "units": (Decimal(100), "count"),
            "dscr": (Decimal("1.5"), "ratio"),
            "price": (Decimal(100), "USD"),
            "market_tier": ("A", "text"),
        },
    )
    service = register(env, buy_box=RuleCheck(references=refs))
    assert service.check("buy_box", env[4]).passed
    refs["units"] = env[6]("units", Decimal(10), "count", fact_id="small")
    register(env, buy_box=RuleCheck(references=refs))
    assert not service.check("buy_box", env[4]).passed


def test_t037_ac4_assumption_ranges_pass_and_planted_failure(env):
    refs = rule_refs(
        env,
        {
            "market_tier": ("A", "text"),
            "asset_class": ("A", "text"),
            "vintage": (Decimal(2000), "year"),
            "rent_growth": (Decimal(".03"), "ratio"),
            "cap_rate": (Decimal(".05"), "ratio"),
        },
    )
    model, assumptions = range_model(env, refs)
    service = register(
        env, model=model, assumptions=assumptions, assumption_ranges=RuleCheck(references=refs)
    )
    assert service.check("assumption_ranges", env[4]).passed
    refs["rent_growth"] = env[6]("rent_growth", Decimal(".5"), "ratio", fact_id="growth")
    register(
        env, model=model, assumptions=assumptions, assumption_ranges=RuleCheck(references=refs)
    )
    assert not service.check("assumption_ranges", env[4]).passed


def test_t037_ac4_policy_bands_pass_and_planted_failure(env):
    refs = rule_refs(
        env,
        {
            "price": (Decimal(100), "USD"),
            "dd_days": (Decimal(30), "days"),
            "close_days": (Decimal(60), "days"),
            "deposit_percent": (Decimal(".02"), "ratio"),
            "financing_contingency": (True, "bool"),
        },
    )
    service = register(env, policy_bands=RuleCheck(references=refs))
    assert service.check("policy_bands", env[4]).passed
    refs["dd_days"] = env[6]("dd_days", Decimal(2), "days", fact_id="short-dd")
    register(env, policy_bands=RuleCheck(references=refs))
    assert not service.check("policy_bands", env[4]).passed


def test_t037_ac4_required_sections_pass_and_planted_empty_or_fake_heading(env):
    service = register(env, required_sections=("Investment thesis", "Risks"))
    env[5].write_text("# Investment thesis\nSolid demand.\n# Risks\nCosts may rise.\n")
    assert service.check("required_sections", env[4]).passed
    env[5].write_text("# Investment thesis\nSolid demand.\n> # Risks\n`# Risks`\n")
    assert not service.check("required_sections", env[4]).passed
    env[5].write_text("# Investment thesis\nSolid demand.\n# Risks\n")
    assert not service.check("required_sections", env[4]).passed


def test_t037_ac4_irr_sanity_pass_and_planted_canonical_flags(env):
    service, inputs, engine, scope, d, _, _, _ = env
    source = ReturnsInput(
        input_id="flows",
        cash_flows=(Decimal(-100), Decimal(110)),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".05"),
    )
    inputs.put_input(scope, "deal", source)
    issue_returns(env, source)
    calc = calculate_returns(source, calc_id="returns", code_version="test")
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="irr",
        unit="ratio",
        function="calculate_returns",
    )
    register(env, returns=(ReturnCheck(reference=ref, input_id="flows"),))
    assert service.check("irr_sanity", d).passed
    forged = calc.model_copy(
        update={"calc_id": "forged", "outputs": {**calc.outputs, "ambiguous": Decimal(1)}}
    )
    SqlVersionedStore(engine, CalcResult).append(forged, scope=scope)
    register(
        env,
        returns=(
            ReturnCheck(reference=ref.model_copy(update={"record_id": "forged"}), input_id="flows"),
        ),
    )
    assert not service.check("irr_sanity", d).passed


def test_t037_ac4_numbers_match_model_pass_and_planted_coincidental_value(env):
    service, inputs, engine, scope, d, path, _, price = env
    source = ReturnsInput(
        input_id="model-input",
        cash_flows=(Decimal(-100), Decimal(110)),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".05"),
    )
    issue_returns(env, source, calc_id="model", model_id="model")
    calc = calculate_returns(source, calc_id="model", code_version="test")
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    ref = EvidenceRef(
        kind="calc",
        record_id="model",
        deal_id="deal",
        key="total_contributions",
        unit="USD",
        function="calculate_returns",
    )
    model = model_contract(env, calc)
    path.write_text("total contributions $100")
    labels = {"total_contributions": ("total contributions",), "price": ("total contributions",)}
    n = extract_numbers(path.read_text())[0]
    citation = NumberCitation(start=n.start, end=n.end, reference=ref)
    register(
        env,
        model=model,
        labels=labels,
        citations=(citation,),
        model_bindings={"total_contributions": ref},
    )
    assert service.check("numbers_match_model", d).passed
    register(
        env,
        citations=(citation.model_copy(update={"reference": price}),),
        model=model,
        labels=labels,
        model_bindings={"total_contributions": ref},
    )
    assert not service.check("numbers_match_model", d).passed


def test_t037_ac4_fragility_pass_and_planted_unconditional_near_flip(env):
    from cre_brain.finance.scenarios import AssumptionRange, FragilityInput
    from cre_brain.gates import FragilityCheck

    service, inputs, engine, scope, d, *_ = env
    ranges = (
        AssumptionRange(
            input_id="range",
            name="reinvest_rate",
            p10=Decimal(".01"),
            base=Decimal(".03"),
            p90=Decimal(".05"),
            downside="decrease",
        ),
    )
    policy = FragilityInput(
        input_id="fragility-policy",
        ranges=ranges,
        metric_key="mirr",
        target=Decimal(".10"),
        fragility_margin=Decimal(".02"),
    )
    inputs.put_input(scope, "deal", policy)
    calculations = {}
    for identity, rate, input_id in (
        ("base", ".03", "base-input"),
        ("downside", ".01", "scenario"),
    ):
        source = ReturnsInput(
            input_id=input_id,
            cash_flows=(Decimal(-100), Decimal(118), Decimal(0)),
            finance_rate=Decimal(".05"),
            reinvest_rate=Decimal(rate),
        )
        issue_returns(env, source, calc_id=identity, model_id="model")
        calc = calculate_returns(source, calc_id=identity, code_version="test")
        SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
        calculations[identity] = calc
    model = model_contract(env, calculations["base"])
    scenario = env[6]("reinvest_rate", Decimal(".01"), "ratio")
    base = EvidenceRef(
        kind="calc",
        record_id="base",
        deal_id="deal",
        key="mirr",
        unit="ratio",
        function="calculate_returns",
    )
    down = base.model_copy(update={"record_id": "downside"})
    check = FragilityCheck(
        input_id=policy.input_id,
        deal_id="deal",
        base=base,
        scenarios=(
            __import__("cre_brain.gates", fromlist=["ScenarioCheck"]).ScenarioCheck(
                input_id="scenario", result=down, assumptions={"reinvest_rate": scenario}
            ),
        ),
    )
    register(env, model=model, fragility=check)
    assert not service.check("fragility", d).passed
    conditional = d.model_copy(update={"status": "conditional", "version": 2})
    inputs.put_plan(scope, conditional, GatePlan(model=model, fragility=check))
    assert service.check("fragility", conditional).passed
    far_source = ReturnsInput(
        input_id="far-base-input",
        cash_flows=(Decimal(-100), Decimal("121.7864077669902912621359223"), Decimal(0)),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".03"),
    )
    issue_returns(env, far_source, calc_id="far-base", model_id="model")
    far = calculate_returns(far_source, calc_id="far-base", code_version="test")
    SqlVersionedStore(engine, CalcResult).append(far, scope=scope)
    far_down_source = far_source.model_copy(
        update={"input_id": "far-down-input", "reinvest_rate": Decimal(".01")}
    )
    issue_returns(env, far_down_source, calc_id="far-down", model_id="model")
    far_down = calculate_returns(far_down_source, calc_id="far-down", code_version="test")
    SqlVersionedStore(engine, CalcResult).append(far_down, scope=scope)
    register(
        env,
        model=model_contract(env, far),
        fragility=check.model_copy(
            update={
                "base": base.model_copy(update={"record_id": "far-base"}),
                "scenarios": (
                    check.scenarios[0].model_copy(
                        update={
                            "input_id": "far-down-input",
                            "result": down.model_copy(update={"record_id": "far-down"}),
                        }
                    ),
                ),
            }
        ),
    )
    assert service.check("fragility", d).passed  # Equality at margin is a sensitivity.


@pytest.mark.parametrize("gate", ["parity", "excel_errors"])
def test_t037_ac4_real_workbook_pass_and_planted_cache_error(env, gate):
    import xml.etree.ElementTree as ET
    import zipfile

    from cre_brain.config import load
    from cre_brain.excel.build_template import build_template
    from cre_brain.excel.writer import build_workbook
    from cre_brain.finance.proforma import ProFormaInput, build_proforma
    from cre_brain.gates import WorkbookCheck

    service, _, engine, scope, d, path, add, _ = env
    service.settings = load().gates
    values = {
        "base_monthly_revenue": "100000",
        "base_monthly_operating_expenses": "40000",
        "annual_revenue_growth": ".03",
        "annual_expense_growth": ".02",
        "vacancy_rate": ".05",
        "credit_loss_rate": ".01",
        "monthly_reserves": "2000",
    }
    for key, value in values.items():
        add(key, Decimal(value), "ratio" if "rate" in key or "growth" in key else "USD/month")
    calc = build_proforma(
        ProFormaInput(
            input_id="base_monthly_revenue",
            projection_months=60,
            **{k: Decimal(v) for k, v in values.items()},
        ),
        calc_id="proforma",
        code_version="test",
    )
    from cre_brain.gates.models import FinanceRecipe

    dependencies = {
        key: EvidenceRef(
            kind="fact",
            record_id=key,
            deal_id="deal",
            key=key,
            unit="ratio" if "rate" in key or "growth" in key else "USD/month",
        )
        for key in values
    }
    env[1].put_recipe(
        scope,
        "deal",
        FinanceRecipe(
            calc_id="proforma",
            function="build_proforma",
            code_version="test",
            source=ProFormaInput(
                input_id="base_monthly_revenue",
                projection_months=60,
                **{k: Decimal(v) for k, v in values.items()},
            ),
            dependencies=dependencies,
        ),
    )
    calc = calc.model_copy(update={"inputs": {key: key for key in values}})
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    template, mapping = build_template(path.parent / "template", gates=service.settings)
    output = path.with_suffix(".xlsx")
    build = build_workbook(
        template,
        mapping,
        output,
        engine=engine,
        scope=scope,
        deal_id="deal",
        task_id="task",
        calculations={"proforma": "proforma"},
        gates=service.settings,
    )
    with zipfile.ZipFile(output) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    for index, sheet in enumerate(("Inputs", "Monthly", "Annual"), 1):
        name = f"xl/worksheets/sheet{index}.xml"
        root = ET.fromstring(files[name])
        for cell in root.findall(".//{*}c"):
            address = f"{sheet}!{cell.get('r')}"
            if address in build.expected and cell.find("{*}f") is not None:
                cell.find("{*}v").text = str(build.expected[address])
        files[name] = ET.tostring(root)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    d = d.model_copy(update={"path": str(output), "kind": DeliverableKind.UW_MODEL})
    register(
        env,
        deliverable=d,
        workbook=WorkbookCheck(
            template=template,
            mapping=mapping,
            deal_id="deal",
            calculations={"proforma": "proforma"},
        ),
    )
    assert service.check(gate, d).passed
    root = ET.fromstring(files["xl/worksheets/sheet2.xml"])
    cell = root.find(".//{*}c[{*}f]")
    cell.set("t", "e")
    cell.find("{*}v").text = "#DIV/0!"
    files["xl/worksheets/sheet2.xml"] = ET.tostring(root)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    assert not service.check(gate, d).passed


def test_t037_ac3_advisory_failures_never_block_and_extraction_adds_gates(env):
    from cre_brain.gates import required_gates

    service = register(env, required_sections=("price",))
    env[5].write_text("# price\nNo numeric claims.\n")
    # IC_MEMO still needs contextual model inputs even without numeric claims.
    register(env, required_sections=("price",), model_bindings={"price": env[7]})
    report = service.check_all(env[4])
    assert "entailment" in report.results
    assert not report.results["entailment"].passed
    assert "entailment" not in report.blocking_failures
    assert not service.check("verifier", env[4]).passed
    assert required_gates(DeliverableKind.SCREEN, extraction=True) == (
        "coverage",
        "checksums",
        "buy_box",
        "number_provenance",
    )


def test_t037_ac4_assumption_domain_bounds_and_stale_sources(env):
    from datetime import date

    from cre_brain.domain import Assumption
    from cre_brain.gates import AssumptionCheck

    service, _, engine, scope, d, _, add, _ = env
    refs = rule_refs(
        env,
        {
            "market_tier": ("A", "text"),
            "asset_class": ("A", "text"),
            "vintage": (Decimal(2000), "year"),
            "rent_growth": (Decimal(".03"), "ratio"),
            "cap_rate": (Decimal(".05"), "ratio"),
        },
    )
    assumption = Assumption(
        key="rent_growth",
        value=Decimal(".03"),
        low=Decimal(".01"),
        high=Decimal(".05"),
        rationale="Trusted policy range",
        sources=["rent_growth"],
        is_proxy=False,
        as_of=date(2026, 10, 4),
        set_by="firm_policy",
    )
    store = SqlVersionedStore(engine, Assumption)
    store.append(assumption, scope=scope, record_id="assumption-growth")
    check = AssumptionCheck(record_id="assumption-growth", deal_id="deal", unit="ratio")
    model, assumptions = range_model(env, refs, existing=check)
    register(
        env, model=model, assumption_ranges=RuleCheck(references=refs), assumptions=assumptions
    )
    assert service.check("assumption_ranges", d).passed
    store.append(
        assumption.model_copy(update={"value": Decimal(".10")}),
        scope=scope,
        record_id="assumption-growth",
    )
    assert not service.check("assumption_ranges", d).passed


def test_t037_ac2_calculation_unit_claim_is_not_authoritative(env):
    service, _, engine, scope, d, path, *_ = env
    source = ReturnsInput(
        input_id="flows",
        cash_flows=(Decimal(-100), Decimal(110)),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".05"),
    )
    env[1].put_input(scope, "deal", source)
    issue_returns(env, source)
    calc = calculate_returns(source, calc_id="returns", code_version="test")
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    path.write_text("irr $0.10\n")
    n = extract_numbers(path.read_text())[0]
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="irr",
        unit="USD",
        function="calculate_returns",
    )
    register(env, citations=(NumberCitation(start=n.start, end=n.end, reference=ref),))
    assert not service.check("number_provenance", d).passed


@pytest.mark.parametrize("fault", ["no_roots", "infinite", "multiple_roots"])
def test_t037_ac4_irr_undefined_ambiguous_contracts(env, fault):
    service, inputs, engine, scope, d, *_ = env
    flows = {
        "no_roots": ("100", "110"),
        "infinite": ("0", "0"),
        "multiple_roots": ("-100", "230", "-132"),
    }[fault]
    source = ReturnsInput(
        input_id="flows",
        cash_flows=tuple(Decimal(v) for v in flows),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".05"),
    )
    inputs.put_input(scope, "deal", source)
    issue_returns(env, source)
    calc = calculate_returns(source, calc_id="returns", code_version="test")
    SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    ref = EvidenceRef(
        kind="calc",
        record_id="returns",
        deal_id="deal",
        key="reported_return" if fault == "multiple_roots" else "root_count",
        unit="ratio" if fault == "multiple_roots" else "count",
        function="calculate_returns",
    )
    citations, labels = [], {}
    if fault == "multiple_roots":
        lines = ["Multiple IRR roots; MIRR fallback is reported."]
        for key in ("root_count", "root:0", "root:1", "mirr"):
            label = (
                "root count"
                if key == "root_count"
                else "root"
                if key.startswith("root:")
                else "MIRR fallback"
            )
            value = (
                str(calc.outputs[key])
                if key == "root_count"
                else str(calc.outputs[key] * 100) + "%"
            )
            lines.append(f"{label} {value}.")
            labels[key] = (label,)
        env[5].write_text("\n".join(lines))
        for n, key in zip(
            extract_numbers(env[5].read_text()),
            ("root_count", "root:0", "root:1", "mirr"),
            strict=True,
        ):
            citations.append(
                NumberCitation(
                    start=n.start,
                    end=n.end,
                    reference=ref.model_copy(
                        update={"key": key, "unit": "count" if key == "root_count" else "ratio"}
                    ),
                )
            )
    register(
        env,
        citations=tuple(citations),
        labels=labels,
        returns=(ReturnCheck(reference=ref, input_id="flows"),),
    )
    result = service.check("irr_sanity", d)
    assert result.passed == (fault == "multiple_roots")
    if fault == "multiple_roots":
        assert calc.outputs["root_count"] == 2 and "irr" not in calc.outputs


@pytest.mark.parametrize(
    "case", ["expired", "future", "naive", "collision", "cycle", "ambiguous_calc"]
)
def test_t037_ac2_invalid_canonical_lineage(env, case):
    from datetime import date

    from cre_brain.domain import DateRange

    service, _, engine, scope, d, path, _, price = env
    if case in {"expired", "future", "naive"}:
        fact = SqlVersionedStore(engine, Fact).get("price", scope=scope)
        updates = {"version": 2}
        if case == "expired":
            updates["valid_time"] = DateRange(end=date(2020, 1, 1))
        elif case == "future":
            updates["known_at"] = datetime(2030, 1, 1, tzinfo=UTC)
        else:
            updates["known_at"] = datetime(2026, 10, 1)
        SqlVersionedStore(engine, Fact).append(fact.model_copy(update=updates), scope=scope)
        price = price.model_copy(update={"version": 2})
    else:
        calc = CalcResult(
            calc_id="price" if case == "collision" else "model",
            fn="model",
            inputs={"input": "model" if case == "cycle" else "price"},
            outputs={"price": Decimal(100)},
            code_version="test",
        )
        SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
        if case == "ambiguous_calc":
            SqlVersionedStore(engine, CalcResult).append(
                calc.model_copy(update={"outputs": {"price": Decimal(200)}}), scope=scope
            )
        price = EvidenceRef(
            kind="calc",
            record_id=calc.calc_id,
            deal_id="deal",
            key="price",
            unit="USD",
            function="model",
        )
    n = extract_numbers(path.read_text())[0]
    register(
        env,
        citations=(NumberCitation(start=n.start, end=n.end, reference=price),),
        model_bindings={"price": price},
    )
    assert not service.check("number_provenance", d).passed


def test_t037_ac2_same_line_equal_value_wrong_context_fails(env):
    service, _, _, _, d, path, add, price = env
    units = add("units", Decimal(100), "count")
    path.write_text("price $100 and units 100\n")
    tokens = extract_numbers(path.read_text())
    register(
        env,
        citations=tuple(NumberCitation(start=n.start, end=n.end, reference=price) for n in tokens),
    )
    assert not service.check("number_provenance", d).passed
    register(
        env,
        citations=(
            NumberCitation(start=tokens[0].start, end=tokens[0].end, reference=price),
            NumberCitation(start=tokens[1].start, end=tokens[1].end, reference=units),
        ),
    )
    assert service.check("number_provenance", d).passed


def test_t037_ac2_exact_ratios_and_negative_signs_ignore_global_context(env):
    service, _, _, _, d, path, add, _ = env
    growth = add("growth", Decimal(".05123456"), "ratio")
    path.write_text("growth 5.123456%\n")
    n = extract_numbers(path.read_text())[0]
    register(env, citations=(NumberCitation(start=n.start, end=n.end, reference=growth),))
    with localcontext() as context:
        context.prec = 1
        assert service.check("number_provenance", d).passed
    path.write_text("growth 5.5%\n")
    n = extract_numbers(path.read_text())[0]
    register(env, citations=(NumberCitation(start=n.start, end=n.end, reference=growth),))
    assert not service.check("number_provenance", d).passed
    loss = add("loss", Decimal("-100"), "USD")
    path.write_text("loss $100\n")
    n = extract_numbers(path.read_text())[0]
    register(env, citations=(NumberCitation(start=n.start, end=n.end, reference=loss),))
    assert not service.check("number_provenance", d).passed


def test_t037_ac4_checksum_typed_money_and_ratio_tolerances(env):
    one, two = env[6]("one", Decimal("100.10")), env[6]("two", Decimal("200.20"))
    total = env[6]("total", Decimal("301.30"))
    checksum = Checksum(name="money", parts=(one, two), total=total, unit="USD")
    service = register(env, checksums=(checksum,))
    assert service.check("checksums", env[4]).passed  # Inclusive configured absolute limit.
    a, b, c = (
        env[6]("a", Decimal(".10"), "ratio"),
        env[6]("b", Decimal(".20"), "ratio"),
        env[6]("c", Decimal(".31"), "ratio"),
    )
    register(env, checksums=(Checksum(name="ratio", parts=(a, b), total=c, unit="ratio"),))
    assert not service.check("checksums", env[4]).passed


def test_t037_ac1_unavailable_backend_and_malformed_provider_fail_closed(env):
    class BrokenInputs:
        def plan(self, scope, deliverable):
            raise RuntimeError("required evidence unavailable")

        def finance_input(self, scope, deal_id, input_id):
            return None

        def input_deals(self, scope, input_id):
            return ()

    service = env[0]
    service.inputs = BrokenInputs()
    assert not service.check("coverage", env[4]).passed
    assert not service.check_all(env[4]).passed


def test_t037_ac1_bound_gate_has_spec_check_signature(env):
    service = register(
        env, coverage=(CoverageField(name="price", doc_id="document", references=(env[7],)),)
    )
    assert service.for_gate("coverage").check(env[4]).passed


def test_t037_ac2_date_fact_identity_pass_and_planted_change(env):
    from datetime import date

    service, _, _, _, d, path, add, _ = env
    ref = add("as_of", date(2026, 10, 4), "date")
    path.write_text("as of 2026-10-04\n")
    tokens = extract_numbers(path.read_text())
    register(
        env, citations=(NumberCitation(start=tokens[0].start, end=tokens[0].end, reference=ref),)
    )
    assert service.check("number_provenance", d).passed
    path.write_text("as of 2026-10-05\n")
    assert not service.check("number_provenance", d).passed


def test_t037_ac4_buy_box_correct_no_go_is_deliverable(env):
    refs = rule_refs(
        env,
        {
            "units": (Decimal(10), "count"),
            "dscr": (Decimal("1.5"), "ratio"),
            "price": (Decimal(100), "USD"),
            "market_tier": ("A", "text"),
        },
    )
    service = register(env, buy_box=RuleCheck(references=refs))
    env[5].write_text("Recommendation: NO_GO\n")
    assert service.check("buy_box", env[4]).passed
    env[5].write_text("Recommendation: GO\n")
    assert not service.check("buy_box", env[4]).passed


@pytest.mark.parametrize("case", ["outside", "favorable", "missing_range", "ambiguous"])
def test_t037_ac4_fragility_joint_ranges_and_ambiguity(env, case):
    from cre_brain.finance.scenarios import AssumptionRange, FragilityInput
    from cre_brain.gates import FragilityCheck, ScenarioCheck

    service, inputs, engine, scope, d, *_ = env
    ranges = (
        AssumptionRange(
            input_id="rent-range",
            name="reinvest_rate",
            p10=Decimal(".01"),
            base=Decimal(".03"),
            p90=Decimal(".05"),
            downside="decrease",
        ),
        AssumptionRange(
            input_id="cap-range",
            name="finance_rate",
            p10=Decimal(".04"),
            base=Decimal(".05"),
            p90=Decimal(".06"),
            downside="increase",
        ),
    )
    source = FragilityInput(
        input_id="policy",
        ranges=ranges,
        metric_key="mirr",
        target=Decimal(".10"),
        fragility_margin=Decimal(".02"),
    )
    inputs.put_input(scope, "deal", source)
    base_source = ReturnsInput(
        input_id="base-input",
        cash_flows=(Decimal(-100), Decimal(118), Decimal(0)),
        finance_rate=Decimal(".05"),
        reinvest_rate=Decimal(".03"),
    )
    issue_returns(env, base_source, calc_id="base", model_id="model")
    base = calculate_returns(base_source, calc_id="base", code_version="test")
    outputs = {"reinvest_rate": Decimal(".01"), "finance_rate": Decimal(".06")}
    if case == "outside":
        outputs["finance_rate"] = Decimal(".07")
    elif case == "favorable":
        outputs["finance_rate"] = Decimal(".04")
    scenario_source = base_source.model_copy(update={"input_id": "scenario", **outputs})
    from cre_brain.gates.models import FinanceRecipe

    for calc_id, item in (("base", base_source), ("downside", scenario_source)):
        # The local canonical fixture owns both numeric scenario parameters.
        if calc_id == "base":
            continue
        inputs.put_recipe(
            scope,
            "deal",
            FinanceRecipe(
                calc_id=calc_id,
                function="calculate_returns",
                code_version="test",
                source=item,
                model_id="model",
                scenario_parameters={
                    "reinvest_rate": "reinvest_rate",
                    "finance_rate": "finance_rate",
                },
            ),
        )
    # Reissue base under a distinct immutable recipe identity for this two-axis model.
    two_source = base_source.model_copy(update={"input_id": "two-base-input"})
    inputs.put_recipe(
        scope,
        "deal",
        FinanceRecipe(
            calc_id="two-base",
            function="calculate_returns",
            code_version="test",
            source=two_source,
            model_id="model",
            scenario_parameters={"reinvest_rate": "reinvest_rate", "finance_rate": "finance_rate"},
        ),
    )
    base = calculate_returns(two_source, calc_id="two-base", code_version="test")
    downside = calculate_returns(scenario_source, calc_id="downside", code_version="test")
    if case == "ambiguous":
        downside = downside.model_copy(
            update={"outputs": {**downside.outputs, "ambiguous": Decimal(1)}}
        )
    for calc in (base, downside):
        SqlVersionedStore(engine, CalcResult).append(calc, scope=scope)
    ref = EvidenceRef(
        kind="calc",
        record_id="two-base",
        deal_id="deal",
        key="mirr",
        unit="ratio",
        function="calculate_returns",
    )
    assumptions = {key: env[6](key, value, "ratio") for key, value in outputs.items()}
    if case == "missing_range":
        assumptions.pop("finance_rate")
    register(
        env,
        model=model_contract(env, base),
        fragility=FragilityCheck(
            input_id="policy",
            deal_id="deal",
            base=ref,
            scenarios=(
                ScenarioCheck(
                    input_id="scenario",
                    result=ref.model_copy(update={"record_id": "downside"}),
                    assumptions=assumptions,
                ),
            ),
        ),
    )
    result = service.check("fragility", d)
    assert result.passed == (case in {"outside", "favorable"})
    if result.passed:
        assert result.metrics["sensitivity_only"] == 1


def test_t037_ac1_invalid_model_bindings_are_unavailable_even_without_numbers(env):
    service = register(env, model_bindings={"price": env[7]})
    env[5].write_text("No quantitative claims.\n")
    assert not service.check("numbers_match_model", env[4]).passed
