"""Command line interface. A thin wrapper over trustreply.core."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from trustreply import __version__
from trustreply.core import ingest_path, parse_questionnaire

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


@app.command()
def questions(
    questionnaire: Annotated[Path, typer.Argument(help="A questionnaire (.xlsx or .csv).")],
    sheet: Annotated[str | None, typer.Option(help="Only read this sheet.")] = None,
    question_col: Annotated[
        str | None, typer.Option(help="Column letter holding the questions, e.g. B.")
    ] = None,
    answer_col: Annotated[
        str | None, typer.Option(help="Column letter for answers, e.g. C.")
    ] = None,
    header_row: Annotated[int | None, typer.Option(help="Row number of the header.")] = None,
    show: Annotated[int, typer.Option(help="How many questions to print.")] = 5,
) -> None:
    """List the questions found in a questionnaire and where each answer will go."""
    try:
        result = parse_questionnaire(
            questionnaire,
            sheet=sheet,
            question_col=question_col,
            answer_col=answer_col,
            header_row=header_row,
        )
    except (FileNotFoundError, ValueError) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Found {len(result.questions)} questions in {result.source}.")
    if not result.answer_column_exists:
        typer.echo("No answer column found; answers will go in a new column.")
    for question in result.questions[:show]:
        typer.echo(f"- {question.id} -> {question.answer_cell}: {question.text[:80]}")
