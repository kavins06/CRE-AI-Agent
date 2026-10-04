"""Built-in release commands operate on a selected offline brain checkout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cre_brain import release

Root = Annotated[Path, typer.Option("--root", help="Brain checkout root (defaults to cwd).")]


def register_cli(app: typer.Typer) -> None:
    group = typer.Typer(help="Build, list and restore content-addressed brain releases.")
    app.add_typer(group, name="release")

    @group.command("build")
    def build(
        root: Root = Path("."),
        firm_playbook_versions: Annotated[
            Path | None, typer.Option(help="JSON mapping of firm IDs to version references only.")
        ] = None,
    ) -> None:
        try:
            versions = None
            if firm_playbook_versions is not None:
                versions = json.loads(firm_playbook_versions.read_text())
            manifest = release.build(root, firm_playbook_versions=versions)
            typer.echo(manifest.release_id)
        except (ValueError, OSError) as exc:
            typer.echo(f"Release build failed: {exc}", err=True)
            raise typer.Exit(1) from exc

    @group.command("list")
    def list_releases(root: Root = Path(".")) -> None:
        try:
            for manifest in release.list_releases(root):
                typer.echo(manifest.release_id)
        except (ValueError, OSError) as exc:
            typer.echo(f"Release list failed: {exc}", err=True)
            raise typer.Exit(1) from exc

    @group.command("rollback")
    def rollback(release_id: str, root: Root = Path(".")) -> None:
        try:
            typer.echo(release.rollback(root, release_id).release_id)
        except (ValueError, OSError) as exc:
            typer.echo(f"Release rollback failed: {exc}", err=True)
            raise typer.Exit(1) from exc
