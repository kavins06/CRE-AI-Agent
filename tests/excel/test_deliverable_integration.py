import json

import openpyxl
import pytest
from test_recalc import engine
from test_template import write

from cre_brain.config import load
from cre_brain.excel.deliverable import recalc_deliverable

__all__ = ["engine"]


@pytest.mark.integration
def test_t020_ac4_bound_deliverable_retains_formulas_caches_and_provenance(
    engine, template, synthetic, tmp_path
):
    build = write(template, synthetic, tmp_path / "deliverable.xlsx")
    output, gate = recalc_deliverable(build, engine, gates=load().gates)
    assert output != build.path
    assert gate.passed, gate.failures
    assert gate.metrics["compared_cells"] == len(build.mapping.entries) == 517
    formulas = openpyxl.load_workbook(output)
    caches = openpyxl.load_workbook(output, data_only=True)
    try:
        for entry in build.mapping.entries:
            cell = formulas[entry.sheet][entry.cell]
            assert (cell.data_type == "f") == (entry.role == "output")
            assert caches[entry.sheet][entry.cell].value is not None
            assert cell.comment is not None
            assert json.loads(cell.comment.text) == build.provenance[entry.address]
    finally:
        formulas.close()
        caches.close()
