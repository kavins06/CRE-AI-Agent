"""Explicit builtin registrar; import performs no discovery, I/O or model calls.

The trusted embedding host installs a registry factory after authenticating the
session. Standalone commands refuse absent host composition. No environment or
seller workspace file can supply TenantScope, policy, gate results or providers.
"""

import sys
from collections.abc import Callable
from typing import Annotated

import typer

from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.runner.tools.transport import missing_context

_host_factory: Callable[[], ToolRegistry] | None = None


def install_host_factory(factory: Callable[[], ToolRegistry]) -> None:
    """Host-only composition hook, never a runner command."""
    global _host_factory
    _host_factory = factory


def host_registry() -> ToolRegistry | None:
    return _host_factory() if _host_factory else None


def register_cli(app: typer.Typer) -> None:
    @app.command("tool")
    def tool(
        name: str,
        args: Annotated[str, typer.Option("--args")] = "{}",
        request_id: Annotated[str | None, typer.Option("--request-id")] = None,
    ) -> None:
        try:
            registry = host_registry()
        except Exception:
            registry = None
        response = (
            registry.call_json(name, args, request_id=request_id) if registry else missing_context()
        )
        typer.echo(canonical(response))

    mcp = typer.Typer(help="Host-authenticated minimal CRE MCP stdio.")

    @mcp.command("serve")
    def mcp_serve() -> None:
        try:
            registry = host_registry()
        except Exception:
            registry = None
        if registry is None:
            typer.echo(canonical(missing_context()), err=True)
            raise typer.Exit(1)
        from cre_brain.runner.tools.transport import serve

        serve(registry, sys.stdin, sys.stdout)

    app.add_typer(mcp, name="mcp")
