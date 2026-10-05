"""Import-safe CLI registrar. Runtime authority is supplied by the trusted host only."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from cre_brain.analyst.record import AdvisoryRecordingSession, record_advisory
from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.policy import HostContext
from cre_brain.runner.record import record_segment
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.tools.json_io import canonical


@dataclass(frozen=True)
class RecordingSession:
    runner: CodexRunner
    segment: SegmentSpec
    workspace: Workspace
    policy: HostContext
    expected_deliverables: tuple[str, ...] = ()


_host_factory: Callable[[str], RecordingSession] | None = None
_advisory_factory: Callable[[str], AdvisoryRecordingSession] | None = None


def install_advisory_record_factory(
    factory: Callable[[str], AdvisoryRecordingSession] | None,
) -> None:
    """Trusted operator only; no credential, host or scope plugins in deal files."""
    global _advisory_factory
    _advisory_factory = factory


def install_record_factory(factory: Callable[[str], RecordingSession] | None) -> None:
    """Embedding host authenticates/selects the box, tools, release, config and caps.

    No environment/module path/deal file may install this hook. Isolated MCP must
    be separately composed with the SAME canonical host registry (T032 seam).
    """
    global _host_factory
    _host_factory = factory


def register_cli(app: typer.Typer) -> None:
    @app.command("record")
    def record(
        request: Annotated[str, typer.Option("--request")],
        output: Annotated[Path, typer.Option("--output")],
        refresh: Annotated[bool, typer.Option("--refresh")] = False,
        advisory_probe: Annotated[
            bool,
            typer.Option("--advisory-probe", help="Public synthetic draft probe, not acceptance."),
        ] = False,
    ) -> None:
        if advisory_probe:
            if _advisory_factory is None:
                typer.echo(
                    canonical(
                        {
                            "status": "refused",
                            "category": "missing_runtime",
                            "message": "Host must authorize a public synthetic advisory probe.",
                        }
                    )
                )
                raise typer.Exit(1)
            try:
                advisory_manifest = asyncio.run(
                    record_advisory(
                        _advisory_factory(request),
                        output,
                        request=request,
                    )
                )
            except Exception:
                typer.echo(
                    canonical(
                        {
                            "status": "refused",
                            "category": "recording_unavailable",
                            "message": "Probe refused; inspect the trusted host journal.",
                        }
                    )
                )
                raise typer.Exit(1) from None
            typer.echo(canonical({"status": "ok", **advisory_manifest}))
            return
        if _host_factory is None:
            typer.echo(
                canonical(
                    {
                        "status": "refused",
                        "category": "missing_runtime",
                        "message": (
                            "Host must supply an authenticated isolated streaming recorder runtime."
                        ),
                    }
                )
            )
            raise typer.Exit(1)
        try:
            session = _host_factory(request)
            manifest = asyncio.run(
                record_segment(
                    session.runner,
                    session.segment,
                    session.workspace,
                    session.policy,
                    output,
                    expected_deliverables=session.expected_deliverables,
                    refresh=refresh,
                )
            )
        except Exception:
            typer.echo(
                canonical(
                    {
                        "status": "refused",
                        "category": "recording_unavailable",
                        "message": (
                            "Recording refused; inspect trusted runtime prerequisites/diagnostics."
                        ),
                    }
                )
            )
            raise typer.Exit(1) from None
        typer.echo(
            canonical(
                {
                    "status": "ok",
                    "evidence": manifest.evidence,
                    "manifest_sha256": manifest.manifest_sha256,
                }
            )
        )
