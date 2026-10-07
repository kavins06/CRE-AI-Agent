"""Synthetic saved caches test gate plumbing, never native recalc/model quality."""

import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from decimal import Decimal

import openpyxl
import pytest

from cre_brain.domain import CalcResult, ClaimType, Fact, Provenance
from cre_brain.excel.build_template import build_template
from cre_brain.excel.writer import build_workbook
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.gates import (
    EvidenceRef,
    FinanceRecipe,
    GatePlan,
    NumberCitation,
    WorkbookCheck,
    extract_numbers,
)
from cre_brain.state.store import SqlVersionedStore


@pytest.fixture
def workbook_env(gate_env):
    service, inputs, engine, scope, d, path, _ = gate_env
    values = {
        "base_monthly_revenue": "100000",
        "base_monthly_operating_expenses": "40000",
        "annual_revenue_growth": ".03",
        "annual_expense_growth": ".02",
        "vacancy_rate": ".05",
        "credit_loss_rate": ".01",
        "monthly_reserves": "2000",
    }
    facts = SqlVersionedStore(engine, Fact)
    for key, value in values.items():
        facts.append(
            Fact(
                fact_id=key,
                deal_id="deal",
                key=key,
                value=Decimal(value),
                unit="ratio" if "rate" in key or "growth" in key else "USD/month",
                claim_type=ClaimType.VERIFIED_FACT,
                provenance=[Provenance(doc_id="synthetic", page=1)],
                known_at=datetime(2026, 10, 1, tzinfo=UTC),
                version=1,
            ),
            scope=scope,
        )
    source = ProFormaInput(
        input_id="base_monthly_revenue",
        projection_months=60,
        **{k: Decimal(v) for k, v in values.items()},
    )
    calc = build_proforma(
        source,
        calc_id="proforma",
        code_version="test",
    )
    SqlVersionedStore(engine, CalcResult).append(
        calc.model_copy(update={"inputs": {key: key for key in values}}), scope=scope
    )
    inputs.put_recipe(
        scope,
        "deal",
        FinanceRecipe(
            calc_id=calc.calc_id,
            function="build_proforma",
            code_version=calc.code_version,
            source=source,
            dependencies={
                key: EvidenceRef(
                    kind="fact",
                    record_id=key,
                    deal_id="deal",
                    key=key,
                    unit="ratio" if "rate" in key or "growth" in key else "USD/month",
                )
                for key in values
            },
        ),
    )
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
    d = d.model_copy(update={"path": str(output)})
    book = openpyxl.load_workbook(output, data_only=True)
    try:
        text = "\n".join(
            cell.value
            for sheet in book
            for row in sheet
            for cell in row
            if isinstance(cell.value, str)
        )
    finally:
        book.close()
    citations, labels = [], {}
    for i, token in enumerate(extract_numbers(text)):
        key = f"calendar_{i}"
        # Persist structural calendar indexes explicitly; no numeric exemption.
        facts.append(
            Fact(
                fact_id=key,
                deal_id="deal",
                key=key,
                value=token.value,
                unit="count",
                claim_type=ClaimType.VERIFIED_FACT,
                provenance=[Provenance(doc_id="synthetic-calendar", page=1)],
                known_at=datetime(2026, 10, 1, tzinfo=UTC),
                version=1,
            ),
            scope=scope,
        )
        ref = EvidenceRef(kind="fact", record_id=key, deal_id="deal", key=key, unit="count")
        citations.append(NumberCitation(start=token.start, end=token.end, reference=ref))
        labels[key] = ("Month", "Year")
    plan = GatePlan(
        workbook=WorkbookCheck(
            template=template,
            mapping=mapping,
            deal_id="deal",
            calculations={"proforma": "proforma"},
        ),
        citations=tuple(citations),
        labels=labels,
    )
    inputs.put_plan(scope, d, plan)
    return service, d, output, files


@pytest.mark.parametrize("hidden", [False, True])
def test_t037_ac2_workbook_unmapped_numeric_cells_fail_closed(workbook_env, hidden):
    service, d, output, files = workbook_env
    assert service.check("number_provenance", d).passed
    root = ET.fromstring(files["xl/worksheets/sheet1.xml"])
    rows = root.find("{*}sheetData")
    row = ET.SubElement(
        rows,
        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row",
        {"r": "20", **({"hidden": "1"} if hidden else {})},
    )
    cell = ET.SubElement(
        row, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c", {"r": "B20", "t": "n"}
    )
    ET.SubElement(cell, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v").text = "777"
    files["xl/worksheets/sheet1.xml"] = ET.tostring(root)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    assert not service.check("number_provenance", d).passed
