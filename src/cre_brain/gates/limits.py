"""Budgets checked before readers, Decimal arithmetic and Fraction construction."""

from decimal import Decimal
from pathlib import Path
from stat import S_ISREG
from zipfile import ZipFile

from pydantic import BaseModel

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PACKAGE_BYTES = 32 * 1024 * 1024


class GateFailure(ValueError):
    """Stable public category; never populated from untrusted exception text."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


def bounded_decimal(value: Decimal) -> Decimal:
    parts = value.as_tuple()
    if (
        not value.is_finite()
        or not isinstance(parts.exponent, int)
        or len(parts.digits) > 4096
        or abs(parts.exponent) > 4096
        or abs(value.adjusted()) > 4096
    ):
        raise GateFailure("resource_limit")
    return value


def bounded_values(value: object) -> None:
    if isinstance(value, Decimal):
        bounded_decimal(value)
    elif isinstance(value, BaseModel):
        bounded_values(value.model_dump())
    elif isinstance(value, dict):
        for item in value.values():
            bounded_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            bounded_values(item)


def bounded_file(path: Path) -> None:
    metadata = path.stat()
    if not S_ISREG(metadata.st_mode):
        raise GateFailure("unsupported_display")
    if metadata.st_size > MAX_FILE_BYTES:
        raise GateFailure("resource_limit")
    if path.suffix.lower() == ".xlsx":
        with ZipFile(path) as archive:
            members = archive.infolist()
            if (
                len(members) > 2000
                or sum(m.file_size for m in members) > MAX_PACKAGE_BYTES
                or len({m.filename for m in members}) != len(members)
                or any(m.flag_bits & 1 for m in members)
            ):
                raise GateFailure("resource_limit")


def bounded_decimal_text(value: object) -> None:
    """Check serialized Decimal size/exponent before the domain decoder runs."""
    import re

    if not isinstance(value, str) or len(value) > 8192:
        raise GateFailure("resource_limit")
    exponent = re.search(r"[eE]([+\-]?\d+)$", value)
    if exponent and (len(exponent[1].lstrip("+-")) > 5 or abs(int(exponent[1])) > 4096):
        raise GateFailure("resource_limit")
    if sum(char.isdigit() for char in value) > 4096:
        raise GateFailure("resource_limit")


def bounded_payload(value: object) -> None:
    if isinstance(value, dict):
        if value.get("type") == "decimal":
            bounded_decimal_text(value.get("value"))
        for key, item in value.items():
            if key == "outputs" and isinstance(item, dict):
                for numeric in item.values():
                    bounded_decimal_text(numeric)
            else:
                bounded_payload(item)
    elif isinstance(value, list):
        for item in value:
            bounded_payload(item)
