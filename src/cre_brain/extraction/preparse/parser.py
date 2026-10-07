"""Deterministic source parsing in the host/control plane, before isolated extraction."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from cre_brain.domain.base import TenantScope
from cre_brain.domain.models import Provenance
from cre_brain.extraction.preparse.files import (
    read_source,
    relative_parts,
    root_identity,
    write_parsed,
)
from cre_brain.extraction.preparse.models import (
    DocId,
    Limits,
    PageAnchor,
    ParsedDocument,
    ParsedPage,
    ParsedTable,
    ParsedText,
    ParserUnavailable,
    PdfContent,
    PreparseError,
    digest,
)
from cre_brain.extraction.preparse.native import csv_table, xlsx_tables
from cre_brain.extraction.preparse.reducto import ReductoAdapter

type Delimiter = Literal[",", ";", "\t", "|"]


def _pdf_worker(raw: bytes, limits: Limits) -> PdfContent:
    environment = {
        "PATH": os.defpath,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as target:
        source.write(raw)
        source.seek(0)
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-m",
                    "cre_brain.extraction.preparse.worker",
                    limits.model_dump_json(),
                ],
                stdin=source,
                stdout=target,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=limits.worker_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PreparseError("PDF worker unavailable or resource limit exceeded") from error
        target.seek(0)
        result = target.read(limits.max_output_bytes + 1)
    if len(result) > limits.max_output_bytes:
        raise PreparseError("PDF output byte limit exceeded")
    if process.returncode != 0:
        if result == b'{"error": "unavailable"}':
            raise ParserUnavailable("Native Docling PDF dependency is unavailable")
        raise PreparseError("PDF parsing failed, was unsupported or exceeded resource limits")
    try:
        return PdfContent.model_validate_json(result)
    except ValidationError as error:
        raise PreparseError("Invalid PDF worker output") from error


@dataclass(frozen=True)
class Preparser:
    """Roots and tenant scope must come from trusted host configuration/authentication.

    Files/directories beneath them must be owned by this process's effective UID.
    Seller-controlled relative paths cannot supply roots, tenant scope, parsers or code.
    """

    raw_root: Path
    output_root: Path
    scope: TenantScope
    limits: Limits = field(default_factory=Limits)
    _raw_identity: tuple[int, int] = field(init=False, repr=False)
    _output_identity: tuple[int, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        raw, out = self.raw_root.absolute(), self.output_root.absolute()
        if raw == out or raw in out.parents or out in raw.parents:
            raise PreparseError("Raw and parsed workspace roots must be disjoint")
        object.__setattr__(self, "raw_root", raw)
        object.__setattr__(self, "output_root", out)
        object.__setattr__(self, "scope", TenantScope.model_validate(self.scope.model_dump()))
        object.__setattr__(self, "limits", Limits.model_validate(self.limits))
        object.__setattr__(self, "_raw_identity", root_identity(raw))
        object.__setattr__(self, "_output_identity", root_identity(out))

    def parse(
        self,
        relative_path: str,
        *,
        doc_id: str,
        csv_delimiter: Delimiter = ",",
        reducto: ReductoAdapter | None = None,
    ) -> ParsedDocument:
        identifier = TypeAdapter(DocId).validate_python(doc_id, strict=True)
        delimiter: Delimiter = TypeAdapter(Delimiter).validate_python(csv_delimiter, strict=True)
        parts = relative_parts(relative_path)
        extension = Path(parts[-1]).suffix.lower()
        if extension not in (".csv", ".xlsx", ".pdf"):
            raise PreparseError("Supported source formats are CSV, XLSX and native-text PDF")
        raw = read_source(
            self.raw_root, self._raw_identity, relative_path, self.limits.max_file_bytes
        )
        source_hash = hashlib.sha256(raw).hexdigest()
        configuration_values = {
            "schema": "1.0.0",
            "parser": (
                "reducto"
                if reducto is not None
                else {
                    ".csv": "native-csv",
                    ".xlsx": "native-xlsx",
                    ".pdf": "docling-native",
                }[extension]
            ),
            "limits": self.limits.model_dump(),
        }
        if extension == ".csv":
            configuration_values["csv_delimiter"] = delimiter
        if extension == ".pdf" and reducto is None:
            configuration_values["pdf"] = "native-threads1-no-images-no-ocr-no-enrichment"
        configuration = digest(configuration_values)
        versions: tuple[tuple[str, str], ...] = (
            (("python", ".".join(map(str, sys.version_info[:3]))),)
            if extension == ".csv"
            else ((("openpyxl", metadata.version("openpyxl")),) if extension == ".xlsx" else ())
        )
        seed = digest(
            (
                self.scope.model_dump(),
                identifier,
                source_hash,
                configuration,
                versions,
            )
        )
        tables: tuple[ParsedTable, ...] = ()
        texts: tuple[ParsedText, ...] = ()
        pages: tuple[ParsedPage, ...] = ()
        warnings = []
        pages_without_text: tuple[int, ...] = ()
        status: Literal["parsed", "needs_review", "empty"] = "parsed"
        if reducto is not None:
            reducto.require_available()
            if extension != ".pdf":
                raise PreparseError("XLSX/CSV must be parsed natively")
            content = reducto.convert(raw, filename=parts[-1], limits=self.limits)
            engine: Literal["native-csv", "native-xlsx", "docling-native", "reducto"] = "reducto"
        elif extension == ".pdf":
            content = _pdf_worker(raw, self.limits)
            engine = "docling-native"
            warnings.append("native_pdf_no_ocr_layout_or_table_inference")
            warnings.append("native_pdf_no_visibility_verification")
        else:
            content = None
            if extension == ".csv":
                engine = "native-csv"
                tables = (csv_table(raw, identifier, seed, self.limits, delimiter),)
            else:
                engine = "native-xlsx"
                tables, external, hidden = xlsx_tables(raw, identifier, seed, self.limits)
                if external:
                    warnings.append("external_links_not_followed")
                if hidden:
                    warnings.append("hidden_sheets_included")
            if not any(table.cells for table in tables):
                status = "empty"
        if content is not None:
            pages = content.pages
            versions = content.parser_versions
            seed = digest((seed, engine, versions))
            texts = tuple(
                ParsedText(
                    text_id=digest((seed, index, text.model_dump())),
                    anchor=PageAnchor(doc_id=identifier, page=text.page, bbox=text.bbox),
                    text=text.text,
                    provenance=Provenance(
                        doc_id=identifier,
                        page=text.page,
                        bbox=text.bbox,
                        quote=text.text,
                    ),
                )
                for index, text in enumerate(content.texts)
            )
            text_pages = {text.anchor.page for text in texts}
            pages_without_text = tuple(page.page for page in pages if page.page not in text_pages)
            if pages_without_text:
                status = "needs_review"
                warnings.append("pages_without_native_text")
        try:
            result = ParsedDocument.model_validate(
                {
                    "doc_id": identifier,
                    "scope": self.scope,
                    "source_name": parts[-1],
                    "source_sha256": source_hash,
                    "source_bytes": len(raw),
                    "parser": engine,
                    "parser_versions": versions,
                    "config_sha256": configuration,
                    "limits": self.limits,
                    "status": status,
                    "tables": tables,
                    "texts": texts,
                    "pages": pages,
                    "pages_without_text": pages_without_text,
                    "warnings": tuple(warnings),
                }
            )
        except ValidationError as error:
            raise PreparseError("Parsed source exceeds bounds or has invalid anchors") from error
        if len(result.model_dump_json().encode()) > self.limits.max_output_bytes:
            raise PreparseError("Parsed JSON byte limit exceeded")
        return result

    def write(self, document: ParsedDocument) -> Path:
        validated = ParsedDocument.model_validate_json(document.model_dump_json())
        if validated.scope != self.scope or validated.limits != self.limits:
            raise PreparseError("Parsed source belongs to a different tenant or resource policy")
        content = json.dumps(
            validated.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        if len(content) > self.limits.max_output_bytes:
            raise PreparseError("Parsed JSON byte limit exceeded")
        return write_parsed(
            self.output_root,
            self._output_identity,
            f"{validated.doc_id}.json",
            content,
        )
