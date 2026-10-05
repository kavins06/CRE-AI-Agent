"""Capture advisory development results, never production Runner transcripts."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from cre_brain.analyst.devin import DevinDraftClient
from cre_brain.analyst.loop import AnalystLoop
from cre_brain.runner.tools import files
from cre_brain.runner.tools.json_io import canonical


@dataclass(frozen=True)
class AdvisoryRecordingSession:
    controller: AnalystLoop
    request: str
    evidence: dict[str, Any]
    run_id: str
    evidence_class: Literal["public_synthetic"] = "public_synthetic"


async def record_advisory(
    session: AdvisoryRecordingSession,
    output: Path,
    *,
    request: str,
) -> dict[str, Any]:
    if (
        session.evidence_class != "public_synthetic"
        or session.request != request
        or not isinstance(session.controller.client, DevinDraftClient)
    ):
        raise ValueError("Host must authorize a public synthetic Devin development probe")
    output = output.absolute()
    if any((ancestor / ".git").exists() for ancestor in (output, *output.parents)):
        raise ValueError("Probe captures must remain outside every Git checkout")
    if any(part.casefold() in {"transcripts", "private-eval", "truth"} for part in output.parts):
        raise ValueError("Advisory probes cannot occupy runtime transcripts or evaluation truth")
    with files.directory(output.parent, ()):
        if output.exists() or output.is_symlink():
            raise ValueError("Use a new capture path; existing evidence is never overwritten")
    result = await session.controller.investigate(
        request=session.request,
        evidence=session.evidence,
        run_id=session.run_id,
    )
    content = canonical(result.model_dump(mode="json")).encode()
    seed = canonical({"request": request, "evidence": session.evidence}).encode()
    manifest = {
        "evidence": "unverified_public_development",
        "publication": "not_authorized",
        "run_id": session.run_id,
        "brain_sha256": result.brain_sha256,
        "seed_sha256": files.digest(seed),
        "result_sha256": files.digest(content),
        "status": result.status,
    }
    manifest["manifest_sha256"] = files.digest(canonical(manifest).encode())
    with files.directory(output.parent, ()) as parent:
        os.mkdir(output.name, mode=0o700, dir_fd=parent)
    files.write(output, ("result.json",), content)
    files.write(output, ("manifest.json",), canonical(manifest).encode())
    # Bind only after both files are durable. Files without this host event are inauthentic.
    with session.controller.registry.transaction() as state:
        state.event(
            "runner_raw",
            {
                "advisory_probe_manifest_hash": manifest["manifest_sha256"],
                "evidence": "unverified_public_development",
            },
        )
    return manifest
