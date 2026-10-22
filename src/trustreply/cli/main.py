"""Command line interface. A thin wrapper over trustreply.core."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from trustreply import __version__
from trustreply.core import ingest_path

app = typer.Typer(help="Answer security questionnaires with cited evidence.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Show the installed version."""
    typer.echo(__version__)


@app.command()
def ingest(
    policies: Annotated[Path, typer.Argument(help="A policy file or a folder of policies.")],
    show: Annotated[int, typer.Option(help="How many sample chunks to print.")] = 3,
) -> None:
    """Read policies and report what was extracted (useful for checking ingestion)."""
    try:
        chunks = ingest_path(policies)
    except (FileNotFoundError, ValueError) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    sources = sorted({chunk.source for chunk in chunks})
    typer.echo(f"Extracted {len(chunks)} chunks from {len(sources)} file(s).")
    for chunk in chunks[:show]:
        preview = chunk.text.replace("\n", " ")[:100]
        typer.echo(f"- [{chunk.citation}] {preview}")
