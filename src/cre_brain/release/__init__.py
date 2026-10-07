"""Immutable global brain/config snapshots; tenant playbooks are version references.

Rollback requires trusted releases and exclusive access to the offline checkout.
Manifest hashes provide integrity, not authorization. It stages both trees,
checks identity/environment before writing, and restores the originals on rename
errors. It never changes protected gate code, process environment, or tenant data.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from cre_brain.config import FILES, Settings, load
from cre_brain.release.manifest import Manifest, Snapshot, checked_relative, content_hash

__all__ = ["Manifest", "build", "list_releases", "policy_confirmation", "read", "rollback"]


def _root(root: Path) -> Path:
    result = root.resolve()
    if not result.is_dir():
        raise ValueError("Release root must be an existing directory")
    return result


def _safe(root: Path, relative: str) -> Path:
    path = root
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Release operation refuses symlink: {relative}")
    return path


def _inventory(root: Path, relative: str) -> list[Path]:
    directory = _safe(root, relative)
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise ValueError(f"Release directory is not a directory: {relative}")
    files = []
    for path in sorted(directory.rglob("*")):
        _safe(root, path.relative_to(root).as_posix())
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f"Release refuses nonregular file: {path.relative_to(root)}")
    return files


def _gate_hash(root: Path) -> str:
    files = _inventory(root, "src/cre_brain/gates")
    hashes = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
        if path.suffix == ".py"
    }
    if not hashes:
        raise ValueError("Missing gate code; cannot pin release")
    return content_hash(hashes)


def _codex_version() -> str | None:
    try:
        result = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0][:256]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temporary = Path(temp.name)
        try:
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
            temp.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def build(root: Path, *, firm_playbook_versions: dict[str, str] | None = None) -> Manifest:
    root = _root(root)
    brain = _safe(root, "brain")
    if not brain.is_dir():
        raise ValueError("Missing brain directory")
    paths = _inventory(root, "brain") + [
        path
        for path in _inventory(root, "config")
        if path.parent == root / "config" and path.suffix == ".yaml"
    ]
    files = {}
    for path in paths:
        payload = path.read_bytes()
        files[path.relative_to(root).as_posix()] = Snapshot(
            sha256=hashlib.sha256(payload).hexdigest(),
            content_base64=base64.b64encode(payload).decode("ascii"),
            mode=stat.S_IMODE(path.stat().st_mode) & 0o777,
        )
    settings = load(_safe(root, "config"))
    body = {
        "schema_version": 1,
        "files": {name: snapshot.model_dump(mode="json") for name, snapshot in files.items()},
        "settings": settings.model_dump(mode="json"),
        "gates_code_hash": _gate_hash(root),
        "codex_cli_version": _codex_version(),
        "firm_playbook_versions": {} if firm_playbook_versions is None else firm_playbook_versions,
    }
    manifest = Manifest.model_validate({**body, "release_id": content_hash(body)})
    manifest.validate_integrity()
    path = _safe(root, f"releases/{manifest.release_id}.json")
    if path.exists():
        if read(root, manifest.release_id) != manifest:
            raise ValueError("Existing immutable release differs")
    else:
        _write_atomic(path, manifest.model_dump_json(indent=2).encode() + b"\n")
    return manifest


def read(root: Path, release_id: str) -> Manifest:
    root = _root(root)
    if not re.fullmatch(r"[a-f0-9]{64}", release_id):
        raise ValueError("Release ID must be a full SHA-256 digest")
    path = _safe(root, f"releases/{release_id}.json")
    try:
        manifest = Manifest.model_validate_json(path.read_bytes())
    except OSError as exc:
        raise ValueError(f"Release not found: {release_id}") from exc
    if manifest.release_id != release_id:
        raise ValueError("Release filename/ID mismatch")
    manifest.validate_integrity()
    required = {f"config/{name}" for name in FILES.values()}
    if not required <= manifest.files.keys():
        raise ValueError("Release missing required config files")
    return manifest


def list_releases(root: Path) -> list[Manifest]:
    root = _root(root)
    directory = _safe(root, "releases")
    if not directory.exists():
        return []
    return [
        read(root, path.stem)
        for path in sorted(directory.glob("*.json"))
        if re.fullmatch(r"[a-f0-9]{64}", path.stem)
    ]


def _policy(settings: Settings) -> dict[str, Any]:
    return settings.model_dump(mode="json", include={"budget", "gates", "toggles"})


def _policies(root: Path, manifest: Manifest) -> dict[str, Any]:
    try:
        proposed = Settings.model_validate(
            {
                section: yaml.safe_load(manifest.files[f"config/{filename}"].content())
                for section, filename in FILES.items()
            }
        )
    except yaml.YAMLError as exc:
        raise ValueError("Release policy contains invalid YAML") from exc
    return {
        "current": {
            "files": _policy(load(root / "config", apply_environment=False)),
            "effective": _policy(load(root / "config")),
        },
        "proposed": {"files": _policy(proposed), "effective": _policy(manifest.settings)},
    }


def _confirmation(release_id: str, policies: dict[str, Any]) -> str:
    return content_hash(
        {
            "action": "rollback-policy",
            "release_id": release_id,
            "current_policy_digest": content_hash(policies["current"]),
            "proposed_policy_digest": content_hash(policies["proposed"]),
        }
    )


def policy_confirmation(root: Path, release_id: str) -> str:
    """Preview confirmation bound to this release and current/proposed policies."""
    root = _root(root)
    manifest = read(root, release_id)
    _inventory(root, "config")
    return _confirmation(release_id, _policies(root, manifest))


def rollback(root: Path, release_id: str, *, policy_confirmation: str | None = None) -> Manifest:
    root = _root(root)
    manifest = read(root, release_id)
    if _gate_hash(root) != manifest.gates_code_hash:
        raise ValueError("Release gate code differs; check out the reviewed code version first")
    if _codex_version() != manifest.codex_cli_version:
        raise ValueError("Release Codex CLI version differs; install the recorded runtime first")
    _inventory(root, "brain")
    _inventory(root, "config")
    policies = _policies(root, manifest)
    confirmation = _confirmation(release_id, policies)
    if (
        policies["current"] != policies["proposed"] or policy_confirmation is not None
    ) and policy_confirmation != confirmation:
        raise ValueError(
            f"Protected policy differs or confirmation is invalid for release {release_id}.\n"
            f"Current policy: {json.dumps(policies['current'], sort_keys=True)}\n"
            f"Proposed policy: {json.dumps(policies['proposed'], sort_keys=True)}\n"
            f"Review the policy change, then repeat with --confirm-policy {confirmation}"
        )
    stage = Path(tempfile.mkdtemp(prefix=".release-", dir=root))
    committed = False
    try:
        (stage / "brain").mkdir()
        current_config = _safe(root, "config")
        if current_config.exists():
            shutil.copytree(current_config, stage / "config")
            for path in (stage / "config").glob("*.yaml"):
                path.unlink()
        else:
            (stage / "config").mkdir()
        for name, snapshot in manifest.files.items():
            path = stage / checked_relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(snapshot.content())
            path.chmod(snapshot.mode)
        if load(stage / "config") != manifest.settings:
            raise ValueError("Release environment differs; restore its config overrides first")
        originals = []
        installed = []
        try:
            for name in ("brain", "config"):
                destination = root / name
                backup = stage / f"previous-{name}"
                if destination.exists():
                    os.replace(destination, backup)
                    originals.append((backup, destination))
                os.replace(stage / name, destination)
                installed.append(destination)
        except BaseException:
            try:
                for destination in reversed(installed):
                    shutil.rmtree(destination)
                for backup, destination in reversed(originals):
                    os.replace(backup, destination)
            except OSError as exc:
                raise OSError(f"Originals retained for manual recovery at {stage}") from exc
            raise
        committed = True
    finally:
        has_backups = any((stage / f"previous-{name}").exists() for name in ("brain", "config"))
        if committed or not has_backups:
            shutil.rmtree(stage)
    return manifest
