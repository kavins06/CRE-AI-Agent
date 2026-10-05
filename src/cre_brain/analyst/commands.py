"""Package-local brain inspection; no model calls or publication at import time."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, TypeAdapter

from cre_brain.analyst.brain import load_brain
from cre_brain.analyst.models import AnalystStep, Review, Role, SpecialistResult


def register_cli(app: typer.Typer) -> None:
    group = typer.Typer(help="Analyst brain inspection; reviewed drafts are not deliverables.")
    app.add_typer(group, name="analyst")

    @group.command("instructions")
    def instructions(
        brain_root: Annotated[Path, typer.Option(help="Trusted installed brain asset root.")],
        role: Annotated[str, typer.Option()] = "lead",
    ) -> None:
        try:
            selected: Role = TypeAdapter(Role).validate_python(role)
            brain = load_brain(brain_root)
            schemas: dict[str, type[BaseModel]] = {
                "lead": AnalystStep,
                "verifier": Review,
                "extraction": SpecialistResult,
                "research": SpecialistResult,
            }
            schema = schemas.get(selected)
            from cre_brain.runner.tools.json_io import canonical

            typer.echo(
                canonical(
                    {
                        "role": selected,
                        "brain_sha256": brain.sha256,
                        "instructions": brain.instructions(selected),
                        "schema": schema.model_json_schema() if schema is not None else None,
                    }
                )
            )
        except (ValueError, OSError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
