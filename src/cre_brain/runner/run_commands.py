"""Import-safe local run registrar; only trusted embedding code installs a host."""

import asyncio
from typing import Annotated

import typer

from cre_brain.runner.orchestration.run import RunHost, RunInput, RunResult, execute_run, refused
from cre_brain.runner.tools.json_io import canonical

_host: RunHost | None = None


def install_run_host(host: RunHost | None) -> None:
    """No environment, module-path, configuration or deal-file plugin mechanism."""
    global _host
    _host = host


def _drive(host: RunHost, supplied: RunInput) -> RunResult:
    """Avoid asyncio.run's unbounded cancellation of uncooperative host tasks.

    Any remaining loop is retained by the embedding host for recovery ownership.
    Retention does not resume work or forcibly terminate a Python coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        return refused("runtime_unavailable")
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(execute_run(host, supplied))
    finally:
        if asyncio.all_tasks(loop):
            host.operations.retain_loop(loop)
        else:
            loop.close()


def register_cli(app: typer.Typer) -> None:
    @app.command("run")
    def run(
        deal: Annotated[str, typer.Option("--deal")],
        request: Annotated[str, typer.Option("--request")],
    ) -> None:
        try:
            supplied = RunInput(deal=deal, request=request)
        except ValueError:
            result = refused("invalid_input")
        else:
            result = refused("missing_runtime") if _host is None else _drive(_host, supplied)
        typer.echo(canonical(result.model_dump(mode="json")))
        if result.status != "ok":
            raise typer.Exit(1)
