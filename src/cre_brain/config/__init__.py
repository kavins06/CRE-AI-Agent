"""Load owner YAML plus CRE_<SECTION>__<FIELD> environment overrides.

Default location: CRE_CONFIG_DIR, or ./config. Runtime callers outside a repository
must pass a config directory explicitly. Missing or invalid configuration fails closed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from cre_brain.config.settings import RoleID, RunnerID, Settings

__all__ = ["RoleID", "RunnerID", "Settings", "live_enabled", "load"]

FILES = {
    "models": "models.yaml",
    "budget": "budget.yaml",
    "gates": "gates.yaml",
    "toggles": "toggles.default.yaml",
}


def _read(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot read config {path.name}") from exc
    if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
        raise ValueError(f"Config {path.name} must be a string-keyed mapping")
    return data


def _apply_env(data: dict[str, Any], section: str) -> None:
    prefix = f"CRE_{section.upper()}__"
    for name, value in sorted(os.environ.items()):
        if not name.startswith(prefix):
            continue
        keys = name[len(prefix) :].lower().split("__")
        if not all(key and key.isidentifier() for key in keys):
            raise ValueError(f"Invalid config override name: {name}")
        target = data
        for key in keys[:-1]:
            child = target.setdefault(key, {})
            if not isinstance(child, dict):
                raise ValueError(f"Config override path is not a mapping: {name}")
            target = child
        try:
            target[keys[-1]] = value if section in {"models", "toggles"} else yaml.safe_load(value)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid config override value for {name}") from exc


def load(config_dir: Path | str | None = None, *, apply_environment: bool = True) -> Settings:
    location = (
        config_dir
        if config_dir is not None
        else (os.environ.get("CRE_CONFIG_DIR") or Path.cwd() / "config")
    )
    directory = Path(location)
    sections = {}
    for section, filename in FILES.items():
        data = _read(directory / filename)
        if apply_environment:
            _apply_env(data, section)
        sections[section] = data
    return Settings.model_validate(sections)


def live_enabled(
    role: str, *, settings: Settings | None = None, config_dir: Path | str | None = None
) -> bool:
    try:
        current = settings or load(config_dir)
        item = next((item for name, item in current.models.roles.items() if name == role), None)
        if item is None or item.runner == "fake":
            return False
        if item.runner == "claude_sdk":
            return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        if item.runner == "openai_agents":
            return bool(os.environ.get("OPENAI_API_KEY", "").strip())
        return (
            subprocess.run(
                ["codex", "login", "status"], capture_output=True, timeout=5, check=False
            ).returncode
            == 0
        )
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return False
