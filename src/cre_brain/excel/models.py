"""Typed reference-template and provenance boundaries."""

from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from cre_brain.domain.models import DomainModel


class CellMapping(DomainModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    sheet: str = Field(min_length=1)
    cell: str = Field(pattern=r"^\$?[A-Z]{1,3}\$?[1-9][0-9]*$")
    source: Literal["fact", "calc"]
    role: Literal["input", "output"]
    key: str = Field(min_length=1)
    calculation: str | None = None
    function: str | None = None
    unit: str
    formula: str | None = None

    @field_validator("cell")
    @classmethod
    def absolute_cell(cls, value: str) -> str:
        import re

        parts = re.fullmatch(r"\$?([A-Z]+)\$?([0-9]+)", value)
        assert parts is not None
        return f"${parts[1]}${parts[2]}"

    @property
    def address(self) -> str:
        return f"{self.sheet}!{self.cell.replace('$', '')}"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.source == "fact" and (self.calculation or self.function or self.formula):
            raise ValueError("Fact cells are literal inputs")
        if self.source == "calc" and (not self.calculation or not self.function):
            raise ValueError("Calc cells need a calculation namespace and function")
        if (self.role == "output") != (self.formula is not None):
            raise ValueError("Outputs retain formulas; solved calculation inputs are literal")
        return self


class TemplateMap(DomainModel):
    schema_version: Literal[1] = 1
    template: Literal["mf_standard"] = "mf_standard"
    entries: list[CellMapping] = Field(min_length=1)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if {e.calculation for e in self.entries if e.source == "calc"} != {"proforma"}:
            raise ValueError("Reference map supports only the proforma calculation namespace")
        for values in (
            [e.name for e in self.entries],
            [e.address for e in self.entries],
            [(e.source, e.calculation, e.key) for e in self.entries],
        ):
            if len(set(values)) != len(values):
                raise ValueError("Template map contains ambiguous names, cells or source keys")
        return self


class WorkbookBuild(DomainModel):
    path: Path
    mapping: TemplateMap
    expected: dict[str, Decimal]
    provenance: dict[str, dict[str, object]]

    @model_validator(mode="after")
    def complete(self) -> Self:
        addresses = {entry.address for entry in self.mapping.entries}
        if set(self.expected) != addresses or set(self.provenance) != addresses:
            raise ValueError("Build requires complete mapped expectation/provenance coverage")
        return self
