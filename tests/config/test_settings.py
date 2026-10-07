"""Validated offline configuration and runner availability contract."""

from __future__ import annotations

import ast
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from pydantic import ValidationError

from cre_brain import config

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    return tmp_path / "config"


def edit(path: Path, key: str, value: object) -> None:
    data = yaml.safe_load(path.read_text())
    data[key] = value
    path.write_text(yaml.safe_dump(data))


def test_t003_ac1_owner_models_roles_profiles_and_budget_defaults() -> None:
    settings = config.load(ROOT / "config")
    assert settings.models.runner == "codex"
    assert {role: item.profile for role, item in settings.models.roles.items()} == {
        "lead": "analyst",
        "extraction": "extractor",
        "verifier": "verifier",
        "classifier": "classifier",
        "reflection": "reflector",
    }
    assert all(item.model == "<owner sets>" for item in settings.models.roles.values())
    budget = settings.budget
    assert budget.segment_max_min == 20
    assert budget.nightly_sessions == 200
    assert budget.nightly_wallclock_h == 10
    assert budget.max_parallel_extractions == 4
    assert budget.max_parallel_sessions == 2
    assert budget.codex_login_max_concurrency == 1
    assert budget.box_reconnect_s > 0
    assert settings.gates.parity_abs == Decimal("1")
    assert settings.gates.parity_rel == Decimal("0.000001")
    assert {"SUM", "NPV", "IRR", "XIRR", "PMT"} <= set(settings.gates.excel_functions)
    assert Decimal(0) < settings.gates.fragility_margin < Decimal(1)
    assert all(value == "off" for value in settings.toggles.model_dump().values())


def test_t003_ac2_environment_overrides_files(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRE_CONFIG_DIR", str(directory))
    monkeypatch.setenv("CRE_BUDGET__SEGMENT_MAX_MIN", "7")
    monkeypatch.setenv("CRE_MODELS__ROLES__LEAD__MODEL", "owner-configured-model")
    monkeypatch.setenv("CRE_TOGGLES__BROWSE", "ask")
    settings = config.load()
    assert settings.budget.segment_max_min == 7
    assert settings.models.roles["lead"].model == "owner-configured-model"
    assert settings.toggles.browse == "ask"
    assert config.load(directory).budget.segment_max_min == 7
    assert yaml.safe_load((directory / "budget.yaml").read_text())["segment_max_min"] == 20


@pytest.mark.parametrize(
    ("filename", "key", "value"),
    [
        ("budget.yaml", "segment_max_min", 0),
        ("budget.yaml", "nightly_sessions", True),
        ("budget.yaml", "max_parallel_extractions", -1),
        ("budget.yaml", "codex_login_max_concurrency", 2),
        ("budget.yaml", "unexpected", 12),
        ("gates.yaml", "parity_abs", "-1"),
        ("gates.yaml", "parity_rel", "NaN"),
        ("gates.yaml", "fragility_margin", "1.2"),
        ("gates.yaml", "excel_functions", ["SUM", "SUM"]),
        ("toggles.default.yaml", "send_loi", "always"),
        ("models.yaml", "runner", "unknown"),
        ("models.yaml", "roles", {}),
    ],
)
def test_t003_ac2_invalid_values_fail_closed(
    directory: Path, filename: str, key: str, value: object
) -> None:
    edit(directory / filename, key, value)
    with pytest.raises(ValidationError):
        config.load(directory)


def test_t003_ac2_missing_bad_files_and_unknown_env_rejected(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRE_BUDGET__TYPO", "5")
    with pytest.raises(ValidationError):
        config.load(directory)
    monkeypatch.delenv("CRE_BUDGET__TYPO")
    (directory / "budget.yaml").write_text("a: [")
    with pytest.raises(ValueError, match="budget.yaml"):
        config.load(directory)
    (directory / "budget.yaml").unlink()
    with pytest.raises(ValueError, match="budget.yaml"):
        config.load(directory)


def test_t003_ac3_codex_status_only_bounded_and_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = Mock(return_value=subprocess.CompletedProcess(["codex"], 0))
    monkeypatch.setattr(config.subprocess, "run", probe)
    assert config.live_enabled("lead", settings=config.load(ROOT / "config"))
    args, kwargs = probe.call_args
    assert args == (["codex", "login", "status"],)
    assert kwargs["timeout"] == 5
    assert kwargs["capture_output"] is True
    probe.return_value.returncode = 1
    assert not config.live_enabled("extraction", settings=config.load(ROOT / "config"))
    probe.side_effect = FileNotFoundError()
    assert not config.live_enabled("lead", settings=config.load(ROOT / "config"))
    probe.side_effect = subprocess.TimeoutExpired("codex", 5)
    assert not config.live_enabled("lead", settings=config.load(ROOT / "config"))


def test_t003_ac3_sdk_keys_fake_and_unknown_role(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = Mock(side_effect=AssertionError("SDK and fake must not probe Codex"))
    monkeypatch.setattr(config.subprocess, "run", probe)
    for runner, key in (("claude_sdk", "ANTHROPIC_API_KEY"), ("openai_agents", "OPENAI_API_KEY")):
        data = yaml.safe_load((directory / "models.yaml").read_text())
        data["runner"] = runner
        for role in data["roles"].values():
            role["runner"] = runner
        (directory / "models.yaml").write_text(yaml.safe_dump(data))
        monkeypatch.delenv(key, raising=False)
        assert not config.live_enabled("lead", settings=config.load(directory))
        monkeypatch.setenv(key, "synthetic-test-key")
        assert config.live_enabled("lead", settings=config.load(directory))
    edit(directory / "models.yaml", "runner", "fake")
    data = yaml.safe_load((directory / "models.yaml").read_text())
    for role in data["roles"].values():
        role["runner"] = "fake"
    (directory / "models.yaml").write_text(yaml.safe_dump(data))
    assert not config.live_enabled("lead", settings=config.load(directory))
    assert not config.live_enabled("unknown", settings=config.load(directory))
    probe.assert_not_called()


def test_t003_ac3_invalid_configuration_is_not_live(directory: Path) -> None:
    (directory / "models.yaml").write_text("invalid: true")
    assert not config.live_enabled("lead", config_dir=directory)


@pytest.mark.parametrize("toggle", ["off", "ask", "on"])
def test_t003_ac2_toggle_environment_is_a_string_enum(
    directory: Path, monkeypatch: pytest.MonkeyPatch, toggle: str
) -> None:
    monkeypatch.setenv("CRE_TOGGLES__BROWSE", toggle)
    assert config.load(directory).toggles.browse == toggle


def model_literals_outside_config(source: Path, configured: set[str]) -> list[str]:
    import re

    violations = []
    family = re.compile(r"^(gpt-|claude-|gemini-|jev-|o[1-9](?:-|$)|sonnet$|opus$|haiku$)", re.I)
    for path in source.rglob("*.py"):
        if path.relative_to(source).parts[:2] == ("cre_brain", "config"):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in configured or family.match(node.value):
                    violations.append(f"{path}:{node.lineno}")
    return violations


def test_t003_ac4_model_names_live_only_in_configuration(tmp_path: Path) -> None:
    configured = {role.model for role in config.load(ROOT / "config").models.roles.values()}
    configured.discard("<owner sets>")
    assert model_literals_outside_config(ROOT / "src", configured) == []
    (tmp_path / "bad.py").write_text('MODEL = "gpt-synthetic"\n')
    assert model_literals_outside_config(tmp_path, configured)
