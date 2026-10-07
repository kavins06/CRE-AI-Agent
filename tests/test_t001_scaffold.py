"""Offline acceptance tests for the repository scaffold (not analyst quality)."""

from __future__ import annotations

import importlib
import importlib.metadata
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from packaging.requirements import Requirement
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "config domain state finance excel rules extraction decisions gates deliverables "
    "runner sandbox connectors memory onboarding control data release"
).split()
BANNED = {"litellm", "dspy", "hyperformula", "marker", "marker-pdf", "ii-agent"}


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=120)


def project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_t001_ac1_installed_distribution_and_entrypoint() -> None:
    from cre_brain import __version__

    dist = importlib.metadata.distribution("cre-brain")
    assert dist.version == __version__
    entry = next(ep for ep in dist.entry_points if ep.name == "cre")
    assert entry.group == "console_scripts"
    assert entry.value == "cre_brain.cli:main"
    assert callable(entry.load())


def test_t001_ac1_all_direct_dependencies_exactly_pinned() -> None:
    config = project()
    assert config["project"]["requires-python"] == ">=3.12,<3.13"
    dependencies = config["project"]["dependencies"] + config["build-system"]["requires"]
    for group in config["dependency-groups"].values():
        dependencies.extend(group)
    for group in config["project"]["optional-dependencies"].values():
        dependencies.extend(group)
    for text in dependencies:
        req = Requirement(text)
        assert len(req.specifier) == 1
        assert next(iter(req.specifier)).operator == "=="
        assert "*" not in str(req.specifier)
        assert not req.url


def test_t001_ac1_locked_graph_has_no_banned_dependencies() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    names = {pkg["name"].lower().replace("_", "-") for pkg in lock["package"]}
    assert not BANNED.intersection(names)
    assert not any(name.startswith(("openhands", "ii-agent")) for name in names)
    for name in ("typer", "pydantic", "pytest", "hypothesis", "ruff", "mypy"):
        assert name in names


def test_t001_ac2_check_executes_only_lint_types_and_offline_units() -> None:
    result = run("make", "--dry-run", "check")
    assert result.returncode == 0, result.stderr
    commands = result.stdout
    assert "ruff check" in commands
    assert "ruff format --check" in commands
    assert "mypy src" in commands
    assert "pytest" in commands
    assert "not integration" in commands
    assert "verify_features" not in commands
    assert "check_task" not in commands
    assert "codex" not in commands


def test_t001_ac2_strict_mypy_rejects_untyped_source(tmp_path: Path) -> None:
    source = tmp_path / "bad.py"
    source.write_text("def missing_types(value):\n    return value\n")
    result = run(
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(ROOT / "pyproject.toml"),
        str(source),
    )
    assert result.returncode == 1
    assert "no-untyped-def" in result.stdout


def test_t001_ac2_ruff_rejects_unused_import(tmp_path: Path) -> None:
    source = tmp_path / "bad.py"
    source.write_text("import os\n")
    result = run(sys.executable, "-m", "ruff", "check", str(source))
    assert result.returncode == 1
    assert "F401" in result.stdout


@given(st.lists(st.integers(), max_size=30))
def test_t001_ac2_hypothesis_is_operational(values: list[int]) -> None:
    assert sorted(reversed(sorted(values))) == sorted(values)


def test_t001_ac2_pytest_strict_markers_and_local_hooks() -> None:
    config = project()["tool"]
    assert config["mypy"]["strict"] is True
    assert "--strict-markers" in config["pytest"]["ini_options"]["addopts"]
    hooks = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    entries = [hook["entry"] for repo in hooks["repos"] for hook in repo["hooks"]]
    assert any("ruff check" in entry for entry in entries)
    assert any("mypy src" in entry for entry in entries)
    for hook in hooks["repos"][0]["hooks"][:2]:
        pattern = hook["files"]
        assert re.search(pattern, "src/cre_brain/cli.py")
        assert re.search(pattern, "tests/test_t001_scaffold.py")
        assert not re.search(pattern, "scripts/check_protected.py")


def test_t001_ac3_real_bootstrap_idempotent_from_unrelated_cwd(tmp_path: Path) -> None:
    target = tmp_path / "checkout with spaces"
    target.mkdir()
    for name in ("pyproject.toml", "uv.lock", "init.sh", ".pre-commit-config.yaml"):
        shutil.copy2(ROOT / name, target / name)
    shutil.copytree(ROOT / "src", target / "src", ignore=shutil.ignore_patterns("__pycache__"))
    before = (target / "uv.lock").read_bytes()
    for _ in range(2):
        result = run(str(target / "init.sh"), cwd=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (target / "uv.lock").read_bytes() == before
    python = target / ".venv/bin/python"
    result = run(str(python), "-c", "import cre_brain; print(cre_brain.__version__)", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == project()["project"]["version"]
    assert not (target / ".env").exists()


def test_t001_ac3_postgres_local_only_compose_contract() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    db = compose["services"]["db"]
    assert db["image"].startswith("postgres:17.")
    assert db["ports"] == ["127.0.0.1:${CRE_POSTGRES_PORT:-5432}:5432"]
    assert "pg_isready" in " ".join(db["healthcheck"]["test"])
    assert db["environment"]["POSTGRES_USER"] == "cre"
    assert db["environment"]["POSTGRES_DB"] == "cre"
    assert "POSTGRES_PASSWORD" in db["environment"]
    assert db["volumes"] == ["db-data:/var/lib/postgresql/data"]
    assert "db-data" in compose["volumes"]
    assert "container_name" not in db
    assert "privileged" not in db


@pytest.mark.parametrize("package", PACKAGES)
def test_t001_ac4_spec_packages_are_importable(package: str) -> None:
    module = importlib.import_module(f"cre_brain.{package}")
    assert Path(module.__file__).name == "__init__.py"


def test_t001_ac4_brain_placeholders_have_honest_status() -> None:
    for name in ("lead", "extraction", "verifier", "classifier", "reflection"):
        content = (ROOT / "brain/prompts" / f"{name}.md").read_text()
        assert "Placeholder" in content
    skill = (ROOT / "brain/skills/multifamily/SKILL.md").read_text()
    assert "name: multifamily" in skill
    assert "Placeholder" in skill
    assert "Placeholder" in (ROOT / "brain/playbook/global.md").read_text()
    assert (ROOT / "brain/prompts/overlays/codex/README.md").is_file()


def test_t001_ac5_cli_help_and_version_work_without_credentials() -> None:
    from cre_brain import __version__
    from cre_brain.cli import create_app

    runner = CliRunner()
    help_result = runner.invoke(create_app(), ["--help"], env={"NO_COLOR": "1"})
    assert help_result.exit_code == 0, help_result.output
    assert "CRE acquisition analyst" in help_result.output
    version = runner.invoke(create_app(), ["--version"])
    assert version.exit_code == 0
    assert version.output.strip() == __version__
    unknown = runner.invoke(create_app(), ["not-a-command"])
    assert unknown.exit_code == 2


def test_t001_ac5_console_script_from_outside_checkout(tmp_path: Path) -> None:
    result = run(str(Path(sys.executable).parent / "cre"), "--help", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "CRE acquisition analyst" in result.stdout


def test_t001_ac5_environment_names_present_without_values() -> None:
    environment = (ROOT / "AGENTS.md").read_text().split("## Environment\n", 1)[1]
    declarations = environment.split("When a runner or key", 1)[0]
    names = set(re.findall(r"`([A-Z][A-Z_]+)`", declarations))
    lines = (ROOT / ".env.example").read_text().splitlines()
    assignments = [line.split("=", 1) for line in lines if line and not line.startswith("#")]
    assert names <= {key for key, _ in assignments}
    assert all(value == "" for _, value in assignments)
    assert len(assignments) == len({key for key, _ in assignments})


def test_t001_ac5_local_artifacts_and_credentials_are_gitignored() -> None:
    paths = [
        ".env",
        ".env.local",
        ".venv/bin/python",
        "private.pem",
        "auth.json",
        "deals/d1/raw.xlsx",
        "transcripts/segment.jsonl",
        "src/cre_brain/__pycache__/x.pyc",
    ]
    result = run("git", "check-ignore", "--no-index", *paths)
    assert result.returncode == 0
    assert set(result.stdout.splitlines()) == set(paths)
    assert run("git", "check-ignore", "--no-index", ".env.example").returncode == 1
