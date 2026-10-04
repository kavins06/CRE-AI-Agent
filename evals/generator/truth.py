"""Scoring-only answers: every computed financial output is a finance CalcResult."""

from hashlib import sha256
from pathlib import Path

import cre_brain
from cre_brain.domain import CalcResult
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.finance.rentroll import normalize_rent_roll
from cre_brain.finance.t12 import ChartOfAccounts, MissingMonthRule, normalize_t12

from ._context import isolated_decimal
from .models import Entry, LatentDeal, Unit


def finance_code_version() -> str:
    root = Path(cre_brain.__file__).resolve().parent
    sources = sorted((root / "finance").glob("*.py")) + sorted((root / "domain").glob("*.py"))
    digest = sha256()
    for source in sources:
        digest.update(str(source.relative_to(root)).encode() + b"\0" + source.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


@isolated_decimal
def calculate_truth(deal: LatentDeal) -> dict[str, CalcResult]:
    deal = LatentDeal.model_validate(deal)
    version = finance_code_version()
    return {
        "rent_roll": normalize_rent_roll(
            list(deal.units), calc_id=f"{deal.deal_id}:rent-roll", code_version=version
        ),
        "t12": normalize_t12(
            list(deal.entries),
            chart=deal.chart,
            missing_month_rule=deal.missing_month_rule,
            calc_id=f"{deal.deal_id}:t12",
            code_version=version,
        ),
        "proforma": build_proforma(
            deal.proforma, calc_id=f"{deal.deal_id}:proforma", code_version=version
        ),
    }


def input_manifest(deal: LatentDeal) -> dict[str, object]:
    inputs: tuple[Unit | Entry | ChartOfAccounts | MissingMonthRule | ProFormaInput, ...] = (
        *deal.units,
        *deal.entries,
        deal.chart,
        deal.missing_month_rule,
        deal.proforma,
    )
    return {item.input_id: item.model_dump(mode="json") for item in inputs}
