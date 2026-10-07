"""Official model-free Docling conversion; OCR/layout/table inference are unsupported."""

from __future__ import annotations

import io
from importlib import metadata
from typing import TYPE_CHECKING

from cre_brain.extraction.preparse.models import (
    Box,
    Budget,
    Limits,
    ParsedPage,
    ParserUnavailable,
    PdfContent,
    PdfText,
    PreparseError,
)

if TYPE_CHECKING:
    from docling_core.types.doc.base import BoundingBox


def normalize_bbox(box: BoundingBox, width: float, height: float) -> Box:
    normalized = box.to_top_left_origin(height)
    values = (float(normalized.l), float(normalized.t), float(normalized.r), float(normalized.b))
    if not (0 <= values[0] <= values[2] <= width and 0 <= values[1] <= values[3] <= height):
        raise PreparseError("PDF bounding box is outside its page")
    return values


def convert_pdf(raw: bytes, limits: Limits) -> PdfContent:
    try:
        from docling.datamodel.base_models import ConversionStatus, DocumentStream, InputFormat
        from docling.datamodel.pipeline_options import NativePdfPipelineOptions
        from docling.document_converter import DocumentConverter, NativePdfFormatOption
        from pypdf import PdfReader
    except ImportError as error:
        raise ParserUnavailable("Native Docling PDF dependency is unavailable") from error
    if metadata.version("docling-slim") != "2.133.0":
        raise ParserUnavailable("Native PDF requires docling-slim 2.133.0")
    if not raw.startswith(b"%PDF-"):
        raise PreparseError("Unsupported PDF header")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise PreparseError("Encrypted PDFs are unsupported")
    count = len(reader.pages)
    if not 1 <= count <= limits.max_pages:
        raise PreparseError("PDF page limit exceeded")
    options = NativePdfPipelineOptions(
        parser_threads=1,
        generate_page_images=False,
        generate_picture_images=False,
        enable_remote_services=False,
        allow_external_plugins=False,
        do_picture_classification=False,
        do_picture_description=False,
        do_chart_extraction=False,
        document_timeout=float(limits.worker_seconds),
    )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: NativePdfFormatOption(pipeline_options=options)},
    )
    conversion = converter.convert(
        DocumentStream(name="source.pdf", stream=io.BytesIO(raw)),
        max_num_pages=limits.max_pages,
        max_file_size=limits.max_file_bytes,
        raises_on_error=True,
    )
    if conversion.status != ConversionStatus.SUCCESS or conversion.errors:
        raise PreparseError("PDF conversion was partial or failed")
    document = conversion.document
    if len(document.pages) != count:
        raise PreparseError("PDF conversion omitted pages")
    pages = tuple(
        ParsedPage(page=number, width=float(page.size.width), height=float(page.size.height))
        for number, page in sorted(document.pages.items())
    )
    budget = Budget(limits)
    texts = []
    for item in document.texts:
        if len(item.prov) != 1 or not isinstance(item.orig, str):
            raise PreparseError("Unexpected native Docling text provenance")
        if not item.orig:
            continue
        provenance = item.prov[0]
        page = document.pages[provenance.page_no]
        budget.add(item.orig)
        texts.append(
            PdfText(
                page=provenance.page_no,
                bbox=normalize_bbox(
                    provenance.bbox, float(page.size.width), float(page.size.height)
                ),
                text=item.orig,
            )
        )
    return PdfContent(
        pages=pages,
        texts=tuple(texts),
        parser_versions=tuple(
            (name, metadata.version(name))
            for name in ("docling-slim", "docling-core", "docling-parse")
        ),
    )
