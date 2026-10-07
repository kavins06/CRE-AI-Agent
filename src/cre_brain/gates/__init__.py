"""Deterministic, canonical-state-backed deliverable gates (SPEC §11)."""

from cre_brain.gates.catalog import CATALOG, REGISTRY, required_gates
from cre_brain.gates.models import (
    AssumptionCheck,
    Checksum,
    CoverageField,
    EvidenceRef,
    FinanceRecipe,
    FragilityCheck,
    GatePlan,
    GateReport,
    InputProvider,
    ModelContract,
    NumberCitation,
    NumberToken,
    ReturnCheck,
    RuleCheck,
    ScenarioCheck,
    TrustedInputs,
    WorkbookCheck,
)
from cre_brain.gates.numbers import extract_numbers
from cre_brain.gates.service import GateService

__all__ = [
    "AssumptionCheck",
    "CATALOG",
    "REGISTRY",
    "Checksum",
    "CoverageField",
    "EvidenceRef",
    "FragilityCheck",
    "FinanceRecipe",
    "ModelContract",
    "GatePlan",
    "GateReport",
    "GateService",
    "InputProvider",
    "NumberCitation",
    "NumberToken",
    "ReturnCheck",
    "RuleCheck",
    "ScenarioCheck",
    "TrustedInputs",
    "WorkbookCheck",
    "extract_numbers",
    "required_gates",
]
