from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cre_brain.knowledge import CacheStore, KnowledgeLibrary, SearchRequest, load_catalog


def register_cli(app: typer.Typer) -> None:
    group = typer.Typer(
        help="Licensed public references; never deal facts or private evaluation data."
    )
    app.add_typer(group, name="knowledge")

    @group.command("catalog")
    def catalog() -> None:
        typer.echo(load_catalog().model_dump_json(indent=2))

    @group.command("import")
    def import_resource(
        resource_id: str,
        cache_dir: Annotated[Path | None, typer.Option()] = None,
        allow_download: Annotated[
            bool, typer.Option(help="Operator opt-in; defaults off.")
        ] = False,
        accept_change: Annotated[
            bool, typer.Option(help="Accept reviewed source hash change.")
        ] = False,
        jurisdiction: Annotated[str, typer.Option()] = "US",
    ) -> None:
        try:
            library = KnowledgeLibrary(
                cache=CacheStore(cache_dir), download_policy="on" if allow_download else "off"
            )
            result = library.import_resource(
                resource_id, jurisdiction=jurisdiction, accept_change=accept_change
            )
            typer.echo(result.model_dump_json(indent=2))
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

    @group.command("search")
    def search(
        query: str,
        cache_dir: Annotated[Path | None, typer.Option()] = None,
        limit: Annotated[int, typer.Option()] = 8,
        max_chars: Annotated[int, typer.Option()] = 12000,
    ) -> None:
        try:
            result = KnowledgeLibrary(cache=CacheStore(cache_dir)).search(
                SearchRequest(query=query, limit=limit, max_chars=max_chars)
            )
            typer.echo(result.model_dump_json())
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
