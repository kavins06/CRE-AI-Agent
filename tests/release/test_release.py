"""Release IDs pin bytes and effective settings, without copying tenant playbooks."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from cre_brain import release
from cre_brain.cli import create_app
from cre_brain.release.manifest import Manifest, content_hash

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "brain").mkdir()
    (tmp_path / "brain/prompt.md").write_bytes(b"synthetic prompt\n")
    (tmp_path / "src/cre_brain/gates").mkdir(parents=True)
    (tmp_path / "src/cre_brain/gates/__init__.py").write_text('"""Synthetic gate."""\n')
    monkeypatch.setattr(
        release.subprocess,
        "run",
        Mock(
            return_value=subprocess.CompletedProcess(
                ["codex", "--version"], 0, stdout="codex-cli synthetic\n", stderr=""
            )
        ),
    )
    return tmp_path


def test_t004_ac1_build_content_addressed_manifest_and_identity(repo: Path) -> None:
    first = release.build(repo, firm_playbook_versions={"firm-synthetic": "version-1"})
    second = release.build(repo, firm_playbook_versions={"firm-synthetic": "version-1"})
    assert first.release_id == second.release_id
    assert len(first.release_id) == 64
    path = repo / "releases" / f"{first.release_id}.json"
    assert path.is_file()
    assert first.codex_cli_version == "codex-cli synthetic"
    assert first.settings.models.runner == "codex"
    assert first.settings.models.roles["lead"].model == "<owner sets>"
    assert first.firm_playbook_versions == {"firm-synthetic": "version-1"}
    assert len(first.gates_code_hash) == 64
    assert {
        "brain/prompt.md",
        "config/models.yaml",
        "config/budget.yaml",
        "config/gates.yaml",
        "config/toggles.default.yaml",
    } <= first.files.keys()
    assert release.read(repo, first.release_id) == first


def test_t004_ac1_all_identity_inputs_change_release(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = release.build(repo).release_id
    edit = repo / "config/models.yaml"
    edit.write_text(edit.read_text() + "# one byte matters\n")
    changed_config = release.build(repo).release_id
    assert original != changed_config
    gate = repo / "src/cre_brain/gates/__init__.py"
    gate.write_text(gate.read_text() + "# changed gate\n")
    changed_gate = release.build(repo).release_id
    assert changed_gate != changed_config
    monkeypatch.setenv("CRE_MODELS__ROLES__LEAD__MODEL", "owner-configured-model")
    changed_model = release.build(repo).release_id
    assert changed_model != changed_gate
    monkeypatch.setattr(
        release.subprocess,
        "run",
        Mock(
            return_value=subprocess.CompletedProcess(
                ["codex"], 0, stdout="codex-cli different\n", stderr=""
            )
        ),
    )
    changed_cli = release.build(repo).release_id
    assert changed_cli != changed_model
    assert (
        release.build(repo, firm_playbook_versions={"firm-synthetic": "v2"}).release_id
        != changed_cli
    )


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("codex", 5)])
def test_t004_ac1_missing_cli_cleanly_recorded(
    repo: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    monkeypatch.setattr(release.subprocess, "run", Mock(side_effect=failure))
    assert release.build(repo).codex_cli_version is None


def test_t004_ac1_never_reads_private_playbook_contents(repo: Path) -> None:
    private = repo / "firms/firm-synthetic/playbook"
    private.mkdir(parents=True)
    (private / "secret.txt").write_text("synthetic private tenant content")
    manifest = release.build(repo, firm_playbook_versions={"firm-synthetic": "v1"})
    assert all(not path.startswith("firms/") for path in manifest.files)
    assert (
        "synthetic private tenant content"
        not in (repo / "releases" / f"{manifest.release_id}.json").read_text()
    )


def test_t004_ac2_cli_build_list_and_rollback(repo: Path) -> None:
    runner = CliRunner()
    app = create_app()
    built = runner.invoke(app, ["release", "build", "--root", str(repo)])
    assert built.exit_code == 0, built.output
    release_id = built.output.strip()
    listing = runner.invoke(app, ["release", "list", "--root", str(repo)])
    assert listing.exit_code == 0, listing.output
    assert release_id in listing.output
    (repo / "brain/prompt.md").write_text("changed")
    rollback = runner.invoke(app, ["release", "rollback", release_id, "--root", str(repo)])
    assert rollback.exit_code == 0, rollback.output
    assert (repo / "brain/prompt.md").read_bytes() == b"synthetic prompt\n"
    assert (
        runner.invoke(app, ["release", "rollback", "../escape", "--root", str(repo)]).exit_code != 0
    )


def test_t004_ac3_one_byte_changes_hash_and_rollback_restores_exact_tree(repo: Path) -> None:
    binary = repo / "brain/binary.dat"
    binary.write_bytes(b"\x00\xff\x01")
    first = release.build(repo)
    original = (repo / "brain/prompt.md").read_bytes()
    (repo / "brain/prompt.md").write_bytes(original + b"!")
    assert release.build(repo).release_id != first.release_id
    (repo / "brain/new.md").write_text("new artifact")
    (repo / "brain/binary.dat").unlink()
    budget = repo / "config/budget.yaml"
    saved_budget = budget.read_bytes()
    budget.write_text(budget.read_text().replace("nightly_sessions: 200", "nightly_sessions: 100"))
    (repo / "config/extra.yaml").write_text("extra: true")
    (repo / "config/local.txt").write_text("preserve non-YAML file")
    release.rollback(
        repo,
        first.release_id,
        policy_confirmation=release.policy_confirmation(repo, first.release_id),
    )
    assert (repo / "brain/prompt.md").read_bytes() == original
    assert binary.read_bytes() == b"\x00\xff\x01"
    assert not (repo / "brain/new.md").exists()
    assert not (repo / "config/extra.yaml").exists()
    assert budget.read_bytes() == saved_budget
    assert (repo / "config/local.txt").read_text() == "preserve non-YAML file"


def test_t004_ac3_tampered_manifest_rejected_before_writes(repo: Path) -> None:
    first = release.build(repo)
    path = repo / "releases" / f"{first.release_id}.json"
    payload = json.loads(path.read_text())
    payload["files"]["../escape"] = payload["files"]["brain/prompt.md"]
    path.write_text(json.dumps(payload))
    (repo / "brain/prompt.md").write_text("keep this")
    with pytest.raises(ValueError):
        release.rollback(repo, first.release_id)
    assert (repo / "brain/prompt.md").read_text() == "keep this"
    assert not (repo.parent / "escape").exists()


def test_t004_ac3_symlinks_cannot_read_or_overwrite_outside(repo: Path) -> None:
    outside = repo / "outside.txt"
    outside.write_text("untouched")
    first = release.build(repo)
    (repo / "brain/link.md").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        release.build(repo)
    with pytest.raises(ValueError, match="symlink"):
        release.rollback(repo, first.release_id)
    assert outside.read_text() == "untouched"


def test_t004_ac3_rollback_cannot_silently_replace_gate_code(repo: Path) -> None:
    first = release.build(repo)
    (repo / "src/cre_brain/gates/__init__.py").write_text("changed protected gate")
    with pytest.raises(ValueError, match="gate"):
        release.rollback(repo, first.release_id)


def test_t004_ac3_environment_mismatch_rejected_before_restore(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = release.build(repo)
    (repo / "brain/prompt.md").write_text("keep this")
    monkeypatch.setenv("CRE_MODELS__ROLES__LEAD__MODEL", "different-env")
    with pytest.raises(ValueError, match="environment"):
        release.rollback(repo, first.release_id)
    assert (repo / "brain/prompt.md").read_text() == "keep this"


def test_t004_ac3_install_error_restores_both_original_trees(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = release.build(repo)
    (repo / "brain/prompt.md").write_text("keep this")
    budget = repo / "config/budget.yaml"
    budget.write_text(budget.read_text() + "# preserve this original too\n")
    original_budget = budget.read_bytes()
    replace = release.os.replace

    def fail_config_install(source: Path, destination: Path) -> None:
        if source.name == "config" and source.parent.name.startswith(".release-"):
            raise OSError("synthetic second-directory installation failure")
        replace(source, destination)

    monkeypatch.setattr(release.os, "replace", fail_config_install)
    with pytest.raises(OSError, match="synthetic"):
        release.rollback(repo, first.release_id)
    assert (repo / "brain/prompt.md").read_text() == "keep this"
    assert budget.read_bytes() == original_budget
    assert not list(repo.glob(".release-*"))


def test_t004_ac3_failed_recovery_preserves_backup_bytes(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = release.build(repo)
    (repo / "brain/prompt.md").write_text("original to recover")
    original_budget = (repo / "config/budget.yaml").read_bytes()
    replace = release.os.replace

    def fail_install_and_recovery(source: Path, destination: Path) -> None:
        if source.name == "config" and source.parent.name.startswith(".release-"):
            raise OSError("synthetic install failure")
        if source.name.startswith("previous-"):
            raise OSError("synthetic recovery failure")
        replace(source, destination)

    monkeypatch.setattr(release.os, "replace", fail_install_and_recovery)
    with pytest.raises(OSError, match="Originals retained"):
        release.rollback(repo, first.release_id)
    backups = list(repo.glob(".release-*"))
    assert len(backups) == 1
    assert (backups[0] / "previous-brain/prompt.md").read_text() == "original to recover"
    assert (backups[0] / "previous-config/budget.yaml").read_bytes() == original_budget


def test_t004_ac2_listing_ignores_nonrelease_json_but_not_corrupt_release(repo: Path) -> None:
    manifest = release.build(repo)
    (repo / "releases/notes.json").write_text("not a release")
    assert release.list_releases(repo) == [manifest]
    (repo / "releases" / ("a" * 64 + ".json")).write_text("corrupt")
    with pytest.raises(ValueError):
        release.list_releases(repo)


@pytest.mark.parametrize("current_version", ["codex-cli changed", None])
def test_t004_ac3_runtime_mismatch_fails_before_any_tree_changes(
    repo: Path, monkeypatch: pytest.MonkeyPatch, current_version: str | None
) -> None:
    manifest = release.build(repo)
    (repo / "brain/prompt.md").write_text("preserve current brain")
    monkeypatch.setattr(release, "_codex_version", lambda: current_version)
    with pytest.raises(ValueError, match="Codex CLI version"):
        release.rollback(repo, manifest.release_id)
    assert (repo / "brain/prompt.md").read_text() == "preserve current brain"
    assert not list(repo.glob(".release-*"))


def test_t004_ac3_offline_release_restores_offline_but_not_under_new_runtime(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(release, "_codex_version", lambda: None)
    manifest = release.build(repo)
    (repo / "brain/prompt.md").write_text("changed offline")
    release.rollback(repo, manifest.release_id)
    assert (repo / "brain/prompt.md").read_bytes() == b"synthetic prompt\n"
    monkeypatch.setattr(release, "_codex_version", lambda: "codex-cli newly installed")
    with pytest.raises(ValueError, match="Codex CLI version"):
        release.rollback(repo, manifest.release_id)


@pytest.mark.parametrize(
    ("filename", "before", "after"),
    [
        ("gates.yaml", 'fragility_margin: "0.02"', 'fragility_margin: "0.50"'),
        ("budget.yaml", "nightly_sessions: 200", "nightly_sessions: 999"),
        ("toggles.default.yaml", 'browse: "off"', 'browse: "on"'),
    ],
)
def test_t004_ac3_self_consistent_malicious_policy_requires_explicit_confirmation(
    repo: Path, filename: str, before: str, after: str
) -> None:
    original = release.build(repo)
    payload = original.model_dump(mode="json", exclude={"release_id"})
    name = f"config/{filename}"
    content = original.files[name].content().decode().replace(before, after).encode()
    assert content != original.files[name].content()
    payload["files"][name]["content_base64"] = base64.b64encode(content).decode()
    payload["files"][name]["sha256"] = hashlib.sha256(content).hexdigest()
    # Build the attack's internally valid settings, then restore owner configuration.
    path = repo / name
    saved = path.read_bytes()
    path.write_bytes(content)
    payload["settings"] = release.load(repo / "config").model_dump(mode="json")
    path.write_bytes(saved)
    attack = Manifest.model_validate({**payload, "release_id": content_hash(payload)})
    attack.validate_integrity()
    (repo / "releases" / f"{attack.release_id}.json").write_text(attack.model_dump_json())
    with pytest.raises(ValueError, match="policy"):
        release.rollback(repo, attack.release_id)
    assert path.read_bytes() == saved
    assert (repo / "brain/prompt.md").read_bytes() == b"synthetic prompt\n"
    assert not list(repo.glob(".release-*"))


def test_t004_ac3_exact_policy_confirmation_is_action_bound_and_stale_safe(repo: Path) -> None:
    first = release.build(repo)
    budget = repo / "config/budget.yaml"
    budget.write_text(budget.read_text().replace("nightly_sessions: 200", "nightly_sessions: 100"))
    token = release.policy_confirmation(repo, first.release_id)
    with pytest.raises(ValueError, match="policy"):
        release.rollback(repo, first.release_id, policy_confirmation="wrong")
    budget.write_text(budget.read_text().replace("nightly_sessions: 100", "nightly_sessions: 101"))
    with pytest.raises(ValueError, match="policy"):
        release.rollback(repo, first.release_id, policy_confirmation=token)
    token = release.policy_confirmation(repo, first.release_id)
    (repo / "brain/prompt.md").write_text("second release")
    second = release.build(repo)
    with pytest.raises(ValueError, match="policy"):
        release.rollback(repo, second.release_id, policy_confirmation=token)
    release.rollback(repo, first.release_id, policy_confirmation=token)
    assert budget.read_bytes() == first.files["config/budget.yaml"].content()
    assert (repo / "brain/prompt.md").read_bytes() == b"synthetic prompt\n"


def test_t004_ac2_cli_displays_policy_diff_and_requires_exact_confirmation(repo: Path) -> None:
    first = release.build(repo)
    (repo / "config/toggles.default.yaml").write_text(
        (repo / "config/toggles.default.yaml").read_text().replace('browse: "off"', 'browse: "ask"')
    )
    runner = CliRunner()
    args = ["release", "rollback", first.release_id, "--root", str(repo)]
    result = runner.invoke(create_app(), args)
    assert result.exit_code != 0
    assert "Current policy" in result.output and "Proposed policy" in result.output
    assert first.release_id in result.output and "--confirm-policy" in result.output
    token = release.policy_confirmation(repo, first.release_id)
    assert token in result.output
    result = runner.invoke(create_app(), args + ["--confirm-policy", token])
    assert result.exit_code == 0, result.output


def test_t004_ac3_environment_cannot_hide_changed_file_policy(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRE_TOGGLES__BROWSE", "off")
    first = release.build(repo)
    path = repo / "config/toggles.default.yaml"
    path.write_text(path.read_text().replace('browse: "off"', 'browse: "on"'))
    with pytest.raises(ValueError, match="policy"):
        release.rollback(repo, first.release_id)
    assert 'browse: "on"' in path.read_text()
    assert not list(repo.glob(".release-*"))


def test_t004_ac3_self_consistent_invalid_yaml_fails_cleanly_before_writes(repo: Path) -> None:
    original = release.build(repo)
    payload = original.model_dump(mode="json", exclude={"release_id"})
    content = b"parity: ["
    payload["files"]["config/gates.yaml"]["content_base64"] = base64.b64encode(content).decode()
    payload["files"]["config/gates.yaml"]["sha256"] = hashlib.sha256(content).hexdigest()
    invalid = Manifest.model_validate({**payload, "release_id": content_hash(payload)})
    (repo / "releases" / f"{invalid.release_id}.json").write_text(invalid.model_dump_json())
    with pytest.raises(ValueError, match="policy.*YAML"):
        release.rollback(repo, invalid.release_id)
    assert (repo / "config/gates.yaml").read_bytes() == original.files[
        "config/gates.yaml"
    ].content()
    assert not list(repo.glob(".release-*"))
