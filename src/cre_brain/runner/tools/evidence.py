"""Canonical scoped references, trusted bindings, and versioned numeric lineage."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from cre_brain.domain import Assumption, CalcResult, ClaimType, Fact
from cre_brain.domain.provenance import usable_anchor
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools.contracts import Reference
from cre_brain.runner.tools.state import ToolState, fingerprint

MODELS: dict[str, type[BaseModel]] = {"fact": Fact, "assumption": Assumption, "calc": CalcResult}


def resolve(
    state: ToolState,
    reference: Reference,
    *,
    trusted: bool = True,
    active: frozenset[str] = frozenset(),
) -> Any:
    ref = Reference.model_validate(reference.model_dump(warnings=False))
    if len(active) >= 20:
        raise Refusal(
            "invalid_input", "Canonical dependency depth exceeds the supported tool limit."
        )
    if ref.record_id in active or not state.fresh(ref.record_id):
        raise Refusal("stale_evidence", "Regenerate stale or cyclic canonical dependencies.")
    model = MODELS[ref.kind]
    records = state.records(model, ref.record_id)
    if not records or len(records) != ref.version:
        raise Refusal("stale_evidence", "Reference must pin the current scoped source version.")
    record = records[-1]
    # Cross-collection IDs can never be used as number identities.
    if any(
        state.records(other, ref.record_id) for name, other in MODELS.items() if name != ref.kind
    ):
        raise Refusal("ambiguous_evidence", "Use unique canonical identities across collections.")
    binding = state.binding(ref.record_id, ref.kind)
    if (
        binding is None
        or binding.get("deal") != state.context.deal_id
        or binding.get("digest") != fingerprint(record)
    ):
        raise Refusal(
            "untrusted_evidence", "Host-authenticated current evidence binding is required."
        )
    if isinstance(record, Fact):
        peers = [
            fact
            for fact in state.all_current(Fact)
            if fact.deal_id == record.deal_id and fact.key == record.key
        ]
        if len(peers) != 1:
            raise Refusal(
                "ambiguous_evidence", "Resolve conflicting source identities for this deal key."
            )
        today = datetime.now(UTC).date()
        if (
            record.deal_id != state.context.deal_id
            or record.key != ref.key
            or record.unit != ref.unit
            or record.known_at.utcoffset() is None
            or record.known_at > datetime.now(UTC)
            or (
                record.valid_time
                and (
                    (record.valid_time.start and record.valid_time.start > today)
                    or (record.valid_time.end and record.valid_time.end < today)
                )
            )
        ):
            raise Refusal(
                "incompatible_evidence",
                "Refresh evidence with the correct deal, key, unit and date.",
            )
        if trusted and (
            record.claim_type != ClaimType.VERIFIED_FACT
            or binding.get("authority") not in {"verified_source", "authorized_user"}
        ):
            raise Refusal(
                "untrusted_evidence", "Quarantined seller claims require host source verification."
            )
        return record.value
    if isinstance(record, Assumption):
        if record.key != ref.key or binding.get("unit") != ref.unit:
            raise Refusal(
                "incompatible_evidence", "Assumption key/unit differs from canonical binding."
            )
        if record.as_of > datetime.now(UTC).date() or not record.rationale.strip():
            raise Refusal(
                "untrusted_evidence", "Assumption requires a dated rationale and source lineage."
            )
        for source in binding["references"]:
            resolve(state, Reference.model_validate(source), active=active | {ref.record_id})
        return record.value
    if isinstance(record, CalcResult):
        if ref.key not in record.outputs or binding["units"].get(ref.key) != ref.unit:
            raise Refusal(
                "incompatible_evidence",
                "Select an existing calculation output with its canonical unit.",
            )
        if len(records) != 1 or not record.inputs or record.code_version != binding["code_version"]:
            raise Refusal(
                "ambiguous_evidence", "Calculation identity must be immutable and fully bound."
            )
        for source in binding["references"]:
            resolve(state, Reference.model_validate(source), active=active | {ref.record_id})
        return record.outputs[ref.key]
    raise Refusal("untrusted_evidence", "Unsupported canonical evidence.")


def number(state: ToolState, ref: Reference, unit: str) -> Decimal:
    if ref.unit != unit:
        raise Refusal(
            "incompatible_evidence", "Use the unit required by the deterministic function."
        )
    value = resolve(state, ref)
    if not isinstance(value, Decimal) or not value.is_finite() or len(value.as_tuple().digits) > 32:
        raise Refusal(
            "invalid_input", "Use a finite stored Decimal with at most 32 significant digits."
        )
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or abs(exponent) > 32:
        raise Refusal("invalid_input", "Stored Decimal exponent is outside supported tool bounds.")
    return value


def screen_fact(state: ToolState, ref: Reference) -> Fact:
    """SCREEN can disclose anchored seller claims; it cannot verify or promote them."""
    if ref.kind != "fact":
        raise Refusal("untrusted_evidence", "SCREEN inputs require canonical anchored facts.")
    resolve(state, ref, trusted=False)
    fact = state.current(Fact, ref.record_id)
    binding = state.binding(ref.record_id, "fact")
    if (
        fact is None
        or binding is None
        or fact.claim_type not in {ClaimType.SELLER_ASSERTION, ClaimType.VERIFIED_FACT}
        or binding.get("authority") not in {"quarantine", "verified_source", "authorized_user"}
    ):
        raise Refusal("untrusted_evidence", "SCREEN requires seller or verified deal evidence.")
    if fact.claim_type == ClaimType.VERIFIED_FACT and binding.get("authority") == "quarantine":
        raise Refusal("untrusted_evidence", "Quarantine cannot authorize verification.")
    if not fact.provenance or any(not usable_anchor(p) for p in fact.provenance):
        raise Refusal(
            "untrusted_evidence", "Headline evidence requires page or sheet/cell anchors."
        )
    return fact
