"""Offline, allowlisted JDM evaluation with exact numeric transport and replayable audit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib import metadata, resources

import zen

from cre_brain.rules.models import (
    AssumptionInput,
    BuyBoxInput,
    Decision,
    EscalationInput,
    EvaluationResult,
    EvaluationTrace,
    LoiInput,
    MissingDataInput,
    RentInput,
    RuleInput,
    RuleMatch,
    TaxInput,
    TraceNode,
    scaled,
)

TABLE_IDS = (
    "buy_box.default",
    "assumption_ranges.mf",
    "loi_policy.default",
    "missing_data_policy",
    "escalation_policy",
    "rent_regulation",
    "tax_reassessment",
)
INPUT_MODELS: dict[str, type[RuleInput]] = dict(
    zip(
        TABLE_IDS,
        (
            BuyBoxInput,
            AssumptionInput,
            LoiInput,
            MissingDataInput,
            EscalationInput,
            RentInput,
            TaxInput,
        ),
        strict=True,
    )
)
type Context = dict[str, str | int | bool | None]


def _json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _hash(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _read_table(table_id: str) -> bytes:
    if table_id not in TABLE_IDS:
        raise ValueError("Unknown table ID")
    return resources.files("cre_brain.rules").joinpath(f"tables/{table_id}.json").read_bytes()


def _table_version(raw: bytes, table_id: str) -> str:
    data = json.loads(raw)
    nodes = data.get("nodes", [])
    if (
        not isinstance(nodes, list)
        or len(nodes) != 3
        or [(n.get("id"), n.get("type")) for n in nodes]
        != [("input", "inputNode"), ("rules", "decisionTableNode"), ("output", "outputNode")]
        or nodes[1].get("content", {}).get("hitPolicy") != "first"
        or [(e.get("sourceId"), e.get("targetId")) for e in data.get("edges", [])]
        != [("input", "rules"), ("rules", "output")]
        or data.get("metadata", {}).get("table_id") != table_id
    ):
        raise ValueError("Bundled table must be an allowlisted input/table/output graph")
    version = data["metadata"]["version"]
    if not isinstance(version, str):
        raise ValueError("Bundled table version must be a string")
    return version


def _context(item: RuleInput) -> tuple[Context, str | None]:
    if isinstance(item, BuyBoxInput):
        p = item.policy
        return {
            "units": item.units,
            "dscr": scaled(item.dscr, 6) if item.dscr is not None else None,
            "price": scaled(item.price, 2) if item.price is not None else None,
            "market_tier": item.market_tier,
            "tier_allowed": item.market_tier in p.allowed_market_tiers,
            "min_units": p.min_units,
            "max_units": p.max_units,
            "min_dscr": scaled(p.min_dscr, 6),
            "max_price": scaled(p.max_price, 2),
        }, None
    if isinstance(item, AssumptionInput):
        profile = next(
            (
                p
                for p in item.policy.profiles
                if p.market_tier == item.market_tier
                and p.asset_class == item.asset_class
                and item.vintage is not None
                and p.min_vintage <= item.vintage <= p.max_vintage
            ),
            None,
        )
        context: Context = {
            "profile_known": profile is not None,
            "rent_growth": scaled(item.rent_growth, 6) if item.rent_growth is not None else None,
            "cap_rate": scaled(item.cap_rate, 6) if item.cap_rate is not None else None,
        }
        if profile:
            context.update(
                {
                    "min_rent_growth": scaled(profile.min_rent_growth, 6),
                    "max_rent_growth": scaled(profile.max_rent_growth, 6),
                    "min_cap_rate": scaled(profile.min_cap_rate, 6),
                    "max_cap_rate": scaled(profile.max_cap_rate, 6),
                }
            )
        return context, profile.profile_id if profile else None
    if isinstance(item, LoiInput):
        lp = item.policy
        return {
            "price": scaled(item.price, 2) if item.price is not None else None,
            "dd_days": item.dd_days,
            "close_days": item.close_days,
            "deposit_percent": (
                scaled(item.deposit_percent, 6) if item.deposit_percent is not None else None
            ),
            "financing_contingency": item.financing_contingency,
            "max_price": scaled(lp.max_price, 2),
            "min_dd_days": lp.min_dd_days,
            "max_dd_days": lp.max_dd_days,
            "min_close_days": lp.min_close_days,
            "max_close_days": lp.max_close_days,
            "max_deposit_percent": scaled(lp.max_deposit_percent, 6),
            "require_financing_contingency": lp.require_financing_contingency,
        }, None
    if isinstance(item, MissingDataInput):
        return {
            "missing": bool(item.missing_fields),
            "critical_missing": bool(set(item.missing_fields) & set(item.policy.critical_fields)),
            "allow_defaults": item.policy.allow_defaults,
        }, None
    if isinstance(item, EscalationInput):
        return {
            "evidence_conflict": item.evidence_conflict,
            "legal_uncertainty": item.legal_uncertainty,
            "policy_exception": item.policy_exception,
            "external_action": item.external_action,
            "material_uncertainty": item.material_uncertainty,
            "require_external_approval": item.policy.require_external_approval,
        }, None
    if isinstance(item, RentInput | TaxInput):
        jp = item.policy
        valid = bool(
            jp
            and jp.verified
            and jp.source_ids
            and jp.status != "unknown"
            and item.jurisdiction != "unknown"
            and jp.jurisdiction == item.jurisdiction
        )
        return {"policy_verified": valid, "status": jp.status if jp else "unknown"}, None
    raise ValueError("Unsupported typed rule input")


def evaluate(table: str, input: RuleInput | Mapping[str, object]) -> EvaluationResult:
    """Classify only; never mutate facts, persist assumptions, or compute finance results.

    Numeric comparisons use cents and millionths, bounded by 2**53-1; unsupported
    types/precision fail rather than round. Only packaged graphs can be loaded.
    """
    if table not in INPUT_MODELS:
        raise ValueError("Unknown table ID")
    model = INPUT_MODELS[table]
    item = model.model_validate(input)
    context, profile_id = _context(item)
    raw = _read_table(table)
    version = _table_version(raw, table)
    if metadata.version("zen-engine") != "2.1.2":
        raise ValueError("Rules require zen-engine 2.1.2")

    def loader(key: str) -> str:
        if key != table:
            raise ValueError("Unknown table ID")
        return raw.decode("utf-8")

    response = zen.ZenEngine({"loader": loader}).evaluate(table, context, {"trace": True})
    result = response["result"]
    decision = Decision.model_validate(
        {**result, "required_checks": tuple(result["required_checks"])}
    )
    nodes = []
    matches = []
    for node in sorted(response["trace"].values(), key=lambda n: n["order"]):
        nodes.append(
            TraceNode(
                node_id=node["id"],
                name=node["name"],
                order=node["order"],
                input_json=_json(node["input"]),
                output_json=_json(node["output"]),
                trace_data_json=_json(node["traceData"]),
            )
        )
        if node["id"] == "rules":
            data = node["traceData"]
            if not isinstance(data, dict) or "rule" not in data:
                raise ValueError("Bundled table must return a matching rule trace")
            matches.append(RuleMatch(rule_id=data["rule"]["_id"], index=data["index"]))
    if len(matches) != 1 or tuple(n.node_id for n in nodes) != ("input", "rules", "output"):
        raise ValueError("Bundled table returned an unexpected trace")
    snapshot = item.model_dump(mode="json")
    policy = snapshot["policy"]
    input_json = _json(snapshot)
    source_ids = tuple(sorted(set(item.source_ids) | set(policy["source_ids"] if policy else ())))
    return EvaluationResult(
        decision=decision,
        trace=EvaluationTrace(
            table_id=table,
            table_version=version,
            table_sha256=_hash(raw),
            engine_version="2.1.2",
            policy_id=policy["policy_id"] if policy else "missing-policy",
            policy_version=policy["version"] if policy else "unverified",
            policy_sha256=_hash(_json(policy)),
            input_json=input_json,
            input_sha256=_hash(input_json),
            source_ids=source_ids,
            assumption_ids=tuple(sorted(set(item.assumption_ids))),
            profile_id=profile_id,
            nodes=tuple(nodes),
            matched_rules=tuple(matches),
        ),
    )
