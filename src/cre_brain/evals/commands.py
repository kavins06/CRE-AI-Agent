"""Builtin CLI adapter; do not import fixture tooling until the command runs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Annotated

import typer


def load_generator() -> ModuleType:
    """Load only this installed editable checkout, never a module from a deal folder."""
    name = "_cre_public_generator"
    if name in sys.modules:
        return sys.modules[name]
    source = Path(__file__).resolve().parents[3] / "evals/generator/__init__.py"
    if not source.is_file():
        raise RuntimeError("Generator requires a source checkout with evals/generator installed.")
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the public fixture generator.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        # A failed optional dependency import must not leave a half-loaded package cached.
        for key in tuple(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]
        raise
    return module


def register_cli(app: typer.Typer) -> None:
    evals = typer.Typer(help="Public developer evaluation fixtures.", no_args_is_help=True)

    @evals.command("gen")
    def generate(
        n: Annotated[int, typer.Option(min=1, max=1000)],
        seed: Annotated[str, typer.Option(help="Public synthetic seed, retained only with truth.")],
        out_packages: Annotated[Path, typer.Option(help="New analyst package directory.")],
        out_truth: Annotated[
            Path, typer.Option(help="New scoring-only directory; never mount it.")
        ],
    ) -> None:
        try:
            load_generator().generate(
                n=n, seed=seed, out_packages=out_packages, out_truth=out_truth
            )
        except (ValueError, OSError, RuntimeError, ImportError) as error:
            # Avoid echoing seed, latent inputs, paths or financial answers to analyst logs.
            typer.echo(f"Generation failed ({type(error).__name__}); no completed batch.", err=True)
            raise typer.Exit(1) from None
        typer.echo(f"Generated {n} public synthetic packages with separately stored truth.")

    app.add_typer(evals, name="evals")
