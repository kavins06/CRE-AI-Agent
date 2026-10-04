"""Seller input documents, with no truth calculation, seed or latent manifest access."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.styles import Font

from ._context import isolated_decimal
from .models import ACCOUNTS, LatentDeal, Layout
from .paths import write_document

RENT_ROLL_COLUMNS: dict[Layout, tuple[str, ...]] = {
    "yardi": (
        "unit_id",
        "unit_type",
        "status",
        "market_rent",
        "contract_rent",
        "monthly_concession",
    ),
    "realpage": (
        "unit_type",
        "unit_id",
        "market_rent",
        "monthly_concession",
        "contract_rent",
        "status",
    ),
    "broker": (
        "unit_id",
        "status",
        "contract_rent",
        "unit_type",
        "monthly_concession",
        "market_rent",
    ),
}
HEADERS = {
    "yardi": (
        "Unit",
        "Floor Plan",
        "Status",
        "Market Rent (USD/month)",
        "Lease Rent (USD/month)",
        "Concession (USD/month)",
    ),
    "realpage": (
        "Unit Type",
        "Apartment",
        "Market (USD/month)",
        "Discount (USD/month)",
        "Scheduled Rent (USD/month)",
        "Occupancy",
    ),
    "broker": (
        "Apt #",
        "Leased / Vacant",
        "Current Rent (USD/month)",
        "Beds",
        "Monthly Incentive (USD/month)",
        "Asking Rent (USD/month)",
    ),
}
FIXED_TIME = datetime(2000, 1, 1)


def _workbook(sheet: str, rows: list[list[object]]) -> bytes:
    book = Workbook()
    worksheet = book.active
    assert worksheet is not None
    worksheet.title = sheet
    book.properties.creator = "CRE public synthetic fixtures"
    book.properties.created = FIXED_TIME
    book.properties.modified = FIXED_TIME
    for row in rows:
        worksheet.append([format(v, "f") if isinstance(v, Decimal) else v for v in row])
    # Keep money as exact decimal text: openpyxl's numeric writer coerces Decimal to float.
    for cell in worksheet[3]:
        cell.font = Font(bold=True)
    worksheet.freeze_panes = "A4"
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()
    # openpyxl uses current wall time for core modified metadata and ZIP members.
    # Normalize both without changing source input lexemes.
    normalized = io.BytesIO()
    with ZipFile(buffer) as source, ZipFile(normalized, "w", compression=ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            content = source.read(name)
            if name == "docProps/core.xml":
                from xml.etree import ElementTree as ET

                root = ET.fromstring(content)
                for field in ("created", "modified"):
                    node = root.find(f"{{http://purl.org/dc/terms/}}{field}")
                    if node is not None:
                        node.text = "2000-01-01T00:00:00Z"
                content = ET.tostring(root, encoding="utf-8")
            entry = ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o600 << 16
            target.writestr(entry, content)
    return normalized.getvalue()


def _write(path: Path, content: bytes) -> None:
    write_document(path, content)


@isolated_decimal
def rent_roll_bytes(deal: LatentDeal, *, layout: Layout, extension: str) -> bytes:
    deal = LatentDeal.model_validate(deal)
    if layout not in RENT_ROLL_COLUMNS or extension not in ("csv", "xlsx"):
        raise ValueError("Rent roll requires yardi/realpage/broker layout and CSV/XLSX format")
    rows: list[list[object]] = [
        [f"Synthetic {layout} style rent roll", deal.deal_id],
        ["As of", deal.as_of.isoformat()],
        list(HEADERS[layout]),
    ]
    for unit in deal.units:
        values = {**unit.model_dump(), "status": "Occupied" if unit.occupied else "Vacant"}
        rows.append([values[key] for key in RENT_ROLL_COLUMNS[layout]])
    if extension == "xlsx":
        return _workbook("Rent Roll", rows)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def render_rent_roll(deal: LatentDeal, path: Path, *, layout: Layout) -> None:
    _write(path, rent_roll_bytes(deal, layout=layout, extension=path.suffix.lstrip(".")))


@isolated_decimal
def t12_bytes(deal: LatentDeal) -> bytes:
    deal = LatentDeal.model_validate(deal)
    months = sorted({e.month for e in deal.entries})
    entries = {(e.month, e.account): e.amount for e in deal.entries}
    rows: list[list[object]] = [
        ["Synthetic T12 - USD/month; expenses shown as positive costs", deal.deal_id],
        ["Reserves are below NOI; excluded from operating expenses"],
        ["Account", *(month.isoformat() for month in months)],
    ]
    rows.extend([[account, *(entries[month, account] for month in months)] for account in ACCOUNTS])
    return _workbook("T12", rows)


def render_t12(deal: LatentDeal, path: Path) -> None:
    if path.suffix != ".xlsx":
        raise ValueError("T12 requires XLSX format")
    _write(path, t12_bytes(deal))


class _PDFText(Protocol):
    def setFont(self, name: str, size: int) -> None: ...
    def setLeading(self, leading: int) -> None: ...
    def textLine(self, line: str) -> None: ...


class _PDFCanvas(Protocol):
    def setTitle(self, title: str) -> None: ...
    def setAuthor(self, author: str) -> None: ...
    def setSubject(self, subject: str) -> None: ...
    def beginText(self, x: int, y: int) -> _PDFText: ...
    def drawText(self, text: _PDFText) -> None: ...
    def showPage(self) -> None: ...
    def save(self) -> None: ...


@isolated_decimal
def om_bytes(deal: LatentDeal) -> bytes:
    deal = LatentDeal.model_validate(deal)
    # Already pinned in the documents extra and dev group; no new dependency.
    canvas_factory = cast(
        Callable[..., _PDFCanvas], import_module("reportlab.pdfgen.canvas").Canvas
    )

    buffer = io.BytesIO()
    canvas = canvas_factory(buffer, pagesize=(612, 792), invariant=1, pageCompression=0)
    canvas.setTitle("Synthetic Offering Memorandum")
    canvas.setAuthor("CRE public synthetic fixtures")
    canvas.setSubject("Public developer fixture; uncalibrated inputs")
    lines = [
        "Synthetic Offering Memorandum",
        f"Property: {deal.deal_id}",
        "Fictional multifamily property; uncalibrated developer fixture",
        f"As of: {deal.as_of.isoformat()}",
        f"Units: {len(deal.units)}",
        f"Year built: {deal.vintage}",
        f"Asking price (USD): {deal.asking_price}",
        "Projection assumptions: collection basis, not gross market rent",
        "Net collected revenue incl. other income (USD/month): "
        f"{deal.proforma.base_monthly_revenue}",
        "Operating expenses incl. property tax (USD/month): "
        f"{deal.proforma.base_monthly_operating_expenses}",
        f"Replacement reserves, below NOI (USD/month): {deal.proforma.monthly_reserves}",
        f"Annual revenue growth (decimal ratio): {deal.proforma.annual_revenue_growth}",
        f"Annual expense growth (decimal ratio): {deal.proforma.annual_expense_growth}",
        "Vacancy and concessions already reflected in collected revenue.",
        "Additional vacancy and credit loss (decimal ratio): 0",
        "Unlevered projection: 12 months; reserves deducted after NOI.",
        "No debt, renovation or tax reassessment scenario is assumed.",
    ]
    text = canvas.beginText(36, 750)
    text.setFont("Helvetica", 9)
    text.setLeading(22)
    for line in lines:
        text.textLine(line)
    canvas.drawText(text)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def render_om(deal: LatentDeal, path: Path) -> None:
    if path.suffix != ".pdf":
        raise ValueError("OM requires PDF format")
    _write(path, om_bytes(deal))
