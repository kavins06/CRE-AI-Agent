"""SPEC §11 catalog. Extraction adds coverage/checksums independently of kind."""

from types import MappingProxyType

from cre_brain.domain import DeliverableKind
from cre_brain.gates.models import GateRegistration

DETERMINISTIC = (
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
)
REGISTRY = MappingProxyType(
    {
        name: GateRegistration(name=name, blocking=name in DETERMINISTIC)
        for name in (*DETERMINISTIC, "entailment", "verifier")
    }
)
_catalog: dict[DeliverableKind, tuple[str, ...]] = {
    kind: ("number_provenance",) for kind in DeliverableKind
}
_catalog.update(
    {
        DeliverableKind.SCREEN: ("coverage", "buy_box", "number_provenance"),
        DeliverableKind.UW_MODEL: (
            "checksums",
            "parity",
            "excel_errors",
            "assumption_ranges",
            "irr_sanity",
            "fragility",
            "number_provenance",
        ),
        DeliverableKind.IC_MEMO: (
            "number_provenance",
            "numbers_match_model",
            "required_sections",
            "entailment",
        ),
        DeliverableKind.LOI: ("policy_bands", "number_provenance", "entailment"),
        DeliverableKind.DD_TRACKER: ("coverage", "number_provenance"),
    }
)
CATALOG = MappingProxyType(_catalog)


def required_gates(kind: DeliverableKind, *, extraction: bool = False) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys((*(("coverage", "checksums") if extraction else ()), *CATALOG[kind]))
    )
