"""The physical verifier runs on disposable hosted CI, never on the shared VPS."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/sandbox-validation.yml"


def test_t031_ac4_ci_uses_hosted_runner_and_unchanged_physical_verifier() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    events = workflow.get("on", workflow.get(True))
    assert events["pull_request"]["branches"] == ["dev"]
    assert {
        ".github/workflows/sandbox-validation.yml",
        "src/cre_brain/sandbox/**",
        "tests/sandbox/**",
        "docker/**",
        "pyproject.toml",
        "uv.lock",
        "scripts/check_task.py",
    } <= set(events["pull_request"]["paths"])
    assert "pull_request_target" not in events
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["sandbox-physical"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == 20
    commands = [step["run"] for step in job["steps"] if "run" in step]
    assert "./init.sh" in commands
    assert "uv run pytest tests/sandbox -q && uv run python scripts/check_task.py T031" in commands
    assert not any("continue-on-error" in step for step in job["steps"])


def test_t031_ac4_ci_cannot_inject_credentials_or_use_shared_host() -> None:
    text = WORKFLOW.read_text()
    workflow = yaml.safe_load(text)
    checkout = next(
        step
        for step in workflow["jobs"]["sandbox-physical"]["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    for step in workflow["jobs"]["sandbox-physical"]["steps"]:
        if "uses" in step:
            _, revision = step["uses"].split("@", maxsplit=1)
            assert len(revision) == 40
            assert all(character in "0123456789abcdef" for character in revision)
    assert "secrets." not in text
    assert "self-hosted" not in text
    assert "DOCKER_HOST" not in text
    assert "DATABASE_URL" not in text
    assert "EVALS_PRIVATE_TOKEN" not in text
    assert "CODEX_API_KEY" not in text
    assert "env" not in workflow
    assert "env" not in workflow["jobs"]["sandbox-physical"]
