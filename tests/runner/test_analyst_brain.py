from pathlib import Path

import pytest

from cre_brain.analyst.brain import load_brain
from cre_brain.analyst.models import AnalystStep, Review

ROOT = Path(__file__).resolve().parents[2] / "brain"


def test_brain_release_loads_operational_roles_and_skills() -> None:
    brain = load_brain(ROOT)
    assert set(brain.roles) == {
        "lead",
        "extraction",
        "research",
        "verifier",
        "classifier",
        "reflection",
    }
    assert {"screen", "multifamily", "underwriting", "diligence", "research", "review"} <= set(
        brain.skills
    )
    assert len(brain.sha256) == 64
    for role in brain.roles:
        prompt = brain.instructions(role)
        assert "Placeholder scaffold" not in prompt
        assert "public_reference_not_deal_fact" in prompt
        assert "finalize_deliverable" in prompt
    assert brain.sha256 == load_brain(ROOT).sha256


def test_brain_rejects_symlink_and_unreviewed_placeholder(tmp_path: Path) -> None:
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "lead.md").symlink_to(ROOT / "prompts" / "lead.md")
    with pytest.raises(ValueError):
        load_brain(tmp_path)


def test_step_is_one_action_not_a_tool_and_decision_combination() -> None:
    with pytest.raises(ValueError):
        AnalystStep.model_validate(
            {
                "turn_id": "turn-a",
                "action": "decide",
                "decision": {
                    "recommendation": "hold",
                    "thesis": "More evidence needed",
                    "reasons": [{"text": "Unverified operations", "references": []}],
                    "conditions": [],
                    "unresolved": [],
                    "change_log": [],
                },
                "tool": {"name": "facts_get", "arguments": {}},
            }
        )


def test_review_cannot_authorize_publication_or_suppress_major_findings() -> None:
    with pytest.raises(ValueError):
        Review.model_validate(
            {
                "turn_id": "turn-a",
                "accepted": True,
                "findings": [
                    {
                        "finding_id": "risk",
                        "severity": "major",
                        "issue": "Unsupported income",
                        "required_action": "Reconcile",
                        "references": [],
                    }
                ],
                "strongest_contrary_case": "Seller income is not collected income",
            }
        )
    with pytest.raises(ValueError):
        Review.model_validate(
            {
                "turn_id": "turn-a",
                "accepted": True,
                "findings": [],
                "strongest_contrary_case": "The evidence supports passing",
                "gate_verdict": "PASS",
            }
        )
