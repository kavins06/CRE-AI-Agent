"""Load only trusted, versioned brain assets, not repository or deal instructions."""

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from cre_brain.analyst.models import Role
from cre_brain.runner.tools import files
from cre_brain.runner.tools.json_io import canonical

ROLES: tuple[Role, ...] = ("lead", "extraction", "research", "verifier", "classifier", "reflection")
SKILLS = ("screen", "multifamily", "underwriting", "diligence", "research", "review")


@dataclass(frozen=True)
class Brain:
    roles: Mapping[Role, str]
    skills: Mapping[str, str]
    playbook: str
    sha256: str

    def instructions(self, role: Role) -> str:
        skill_names = {
            "lead": SKILLS,
            "extraction": ("multifamily",),
            "research": ("research",),
            "verifier": ("review", "underwriting"),
            "classifier": (),
            "reflection": ("review",),
        }[role]
        return "\n\n".join(
            (self.roles[role], self.playbook, *(self.skills[name] for name in skill_names))
        )


def load_brain(root: Path) -> Brain:
    root = Path(os.path.abspath(root))
    assets: dict[str, str] = {}

    def read(relative: str) -> str:
        try:
            text = files.read(root, root / relative).decode("utf-8")
        except OSError as exc:
            raise ValueError("Brain assets must be regular non-symlink files") from exc
        if not text.strip() or "Placeholder scaffold" in text:
            raise ValueError("Brain assets must be operational, nonempty and reviewed")
        assets[relative] = text
        return text

    roles = {role: read(f"prompts/{role}.md") for role in ROLES}
    playbook = read("playbook/global.md")
    skills = {name: read(f"skills/{name}/SKILL.md") for name in SKILLS}
    if sum(len(text.encode()) for text in assets.values()) > 262144:
        raise ValueError("Brain exceeds instruction budget")
    digest = hashlib.sha256(canonical(assets).encode()).hexdigest()
    return Brain(
        roles=MappingProxyType(roles),
        skills=MappingProxyType(skills),
        playbook=playbook,
        sha256=digest,
    )
