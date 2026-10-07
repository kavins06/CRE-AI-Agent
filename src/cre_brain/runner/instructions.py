"""Generate a narrow, trusted asset set, never copy a repository/deal directory."""

import hashlib
import json
from pathlib import Path

from cre_brain.domain import DeliverableKind
from cre_brain.runner.segment import SegmentSpec
from cre_brain.runner.streaming import InstructionBundle
from cre_brain.runner.tools import files
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry

MAX_BUNDLE_BYTES = 2097152


def generate(
    brain_root: Path,
    seg: SegmentSpec,
    registry: ToolRegistry,
    model_provider: str,
    *,
    firm_summary: str = "",
    user_memory: str = "",
) -> InstructionBundle:
    """brain_root, summaries and registry are supplied by the authenticated host.

    Config contains no keys/auth paths. Secrets are provisioned only by the owner
    adapter. Instruction pickup and these candidate config settings require a
    capability verification in the installed isolated runtime before live use.
    """
    assets: dict[str, bytes] = {}
    lead = files.read(brain_root, brain_root / "prompts/lead.md").decode("utf-8")
    playbook_path = brain_root / "playbook/global.md"
    public_playbook = (
        files.read(brain_root, playbook_path).decode("utf-8") if playbook_path.exists() else ""
    )
    overlays = [
        files.read(brain_root, path).decode("utf-8")
        for path in sorted((brain_root / "prompts/overlays/codex").glob("*.md"))
    ]
    catalog = "Deliverable catalog\n" + "\n".join(kind.value for kind in DeliverableKind)
    assets["AGENTS.md"] = "\n\n".join(
        (
            lead,
            *overlays,
            "Public playbook\n" + public_playbook,
            "Firm playbook\n" + firm_summary,
            "User memory\n" + user_memory,
            catalog,
        )
    ).encode()
    # Read only explicit skill trees. No symlinks, credentials, Python repo or truth.
    skill_root = brain_root / "skills"
    for path in sorted(skill_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Trusted skill assets must not contain symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(skill_root)
        if len(relative.parts) < 2 or not (
            relative.name == "SKILL.md" or relative.parts[1] in {"scripts", "references", "assets"}
        ):
            continue
        assets[".agents/skills/" + relative.as_posix()] = files.read(brain_root, path)
    role = registry.settings.models.roles["lead"]
    quote = json.dumps  # JSON basic strings are also TOML basic strings.
    config = (
        f"model = {quote(role.model)}\nmodel_provider = {quote(model_provider)}\n"
        'approval_policy = "never"\nsandbox_mode = "workspace-write"\n'
        'web_search = "disabled"\nallow_login_shell = false\n'
        'cli_auth_credentials_store = "file"\n[features]\n'
        "multi_agent = false\nplugins = false\napps = false\n"
        "skill_mcp_dependency_install = false\n"
        f"[profiles.{role.profile}]\nmodel = {quote(role.model)}\n"
        f"model_provider = {quote(model_provider)}\n"
        '[mcp_servers.cre]\ncommand = "cre"\nargs = ["mcp", "serve"]\n'
        'default_tools_approval_mode = "approve"\n'
    )
    assets[".codex/config.toml"] = config.encode()
    if sum(len(data) for data in assets.values()) > MAX_BUNDLE_BYTES:
        raise ValueError("Trusted instruction bundle exceeds limit")
    digest = hashlib.sha256(
        canonical(
            {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()}
        ).encode()
    ).hexdigest()
    return InstructionBundle(cwd=seg.cwd, files=assets, sha256=digest)
