"""Single CLI, extended by package-local cli*.py modules with register_cli(app).

Registration must be side-effect-free; optional dependencies belong inside commands.
Plugins may register commands or Typer groups, never live model calls at import time.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable, Iterator
from types import ModuleType
from typing import Annotated

import typer
from typer.main import get_command

import cre_brain
from cre_brain import __version__


def discover_plugins() -> Iterator[ModuleType]:
    """Discover only trusted installed modules; never scan the user's deal folder."""
    names = sorted(
        info.name
        for info in pkgutil.walk_packages(cre_brain.__path__, prefix="cre_brain.")
        if not info.ispkg
        and (
            info.name.rsplit(".", 1)[-1] == "cli" or info.name.rsplit(".", 1)[-1].startswith("cli_")
        )
        and info.name != __name__
    )
    for name in names:
        yield importlib.import_module(name)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def _validate_names(app: typer.Typer) -> None:
    names = [
        info.name or info.callback.__name__.lower().replace("_", "-")
        for info in app.registered_commands
        if info.callback
    ]
    for group in app.registered_groups:
        if not group.name:
            raise ValueError("CLI groups must have an explicit name.")
        if group.typer_instance is None:
            raise ValueError("CLI groups must provide a Typer instance.")
        names.append(group.name)
        _validate_names(group.typer_instance)
    if len(names) != len(set(names)):
        raise ValueError("Duplicate CLI command or group name.")


def create_app(*, plugins: Iterable[ModuleType] | None = None) -> typer.Typer:
    """Create a fresh app; supplied plugins replace its command registry for testing."""
    app = typer.Typer(
        help="CRE acquisition analyst brain: deterministic tools and orchestration.",
        no_args_is_help=True,
        pretty_exceptions_enable=False,
        add_completion=False,
    )

    @app.callback()
    def root(
        version: Annotated[
            bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
        ] = False,
    ) -> None:
        pass

    root_callback = app.registered_callback
    if plugins is None:
        from cre_brain.knowledge.commands import register_cli as register_knowledge
        from cre_brain.release.commands import register_cli
        from cre_brain.runner.tools.tools_commands import register_cli as register_tools

        register_cli(app)
        register_knowledge(app)
        register_tools(app)
    for module in discover_plugins() if plugins is None else plugins:
        if not module.__name__.startswith("cre_brain."):
            raise ValueError("CLI plugins must be installed under cre_brain.")
        register = getattr(module, "register_cli", None)
        if not callable(register):
            raise ValueError(f"CLI plugin {module.__name__} must define register_cli(app).")
        register(app)
        if app.registered_callback is not root_callback:
            raise ValueError("CLI plugins must not replace the root callback.")

    _validate_names(app)
    command = get_command(app)
    if not hasattr(command, "commands"):
        raise ValueError("CRE must remain a command group.")
    return app


def main() -> None:
    create_app()()
