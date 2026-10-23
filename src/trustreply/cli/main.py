"""Command line interface. A thin wrapper over trustreply.core."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from trustreply import __version__
from trustreply.core import (
    LLMError,
    PolicyIndex,
    draft_answer,
    get_client,
    ingest_path,
    parse_questionnaire,
    verify_answer,
)
from trustreply.core.models import Question

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


@app.command()
def search(
    policies: Annotated[Path, typer.Argument(help="A policy file or a folder of policies.")],
    question: Annotated[str, typer.Argument(help="The question to find evidence for.")],
    top: Annotated[int, typer.Option(help="How many matches to show.")] = 3,
) -> None:
    """Show which policy passages best match a question (the evidence the AI will see)."""
    try:
        index = PolicyIndex(ingest_path(policies))
    except (FileNotFoundError, ValueError) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    hits = index.search(question, top_k=top)
    if not hits:
        typer.echo("No evidence found in the policies. This would be flagged as a gap.")
        return
    for hit in hits:
        preview = hit.chunk.text.replace("\n", " ")[:140]
        typer.echo(f"- {hit.score:.2f} [{hit.chunk.citation}] {preview}")


@app.command()
def draft(
    policies: Annotated[Path, typer.Argument(help="A policy file or a folder of policies.")],
    question: Annotated[str, typer.Argument(help="The question to answer.")],
    top: Annotated[int, typer.Option(help="How many policy passages the model may see.")] = 5,
    verify: Annotated[
        bool,
        typer.Option(
            "--verify/--no-verify",
            help="Check the cited passages really support the answer (one extra model call).",
        ),
    ] = True,
) -> None:
    """Draft a cited answer to one question (the model sees only matching policy passages)."""
    try:
        index = PolicyIndex(ingest_path(policies))
        hits = index.search(question, top_k=top)
        client = get_client() if hits else None
    except (FileNotFoundError, ValueError, LLMError) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    if hits:
        typer.echo(
            f"Sending the question and {len(hits)} matching policy passage(s) to "
            f"{getattr(client, 'provider', 'the AI model')}...",
            err=True,
        )
    item = Question(id="Q", text=question, row=1, question_col="A", answer_col="B")
    try:
        answer = draft_answer(item, hits, client)  # type: ignore[arg-type]
        if verify and client is not None:
            answer = verify_answer(item, answer, client)
    except LLMError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    if answer.is_gap:
        typer.secho("GAP - needs a human answer", fg=typer.colors.YELLOW, bold=True)
        typer.echo(answer.note or "")
        return
    typer.secho(
        f"{answer.verdict.upper()} (confidence: {answer.confidence})",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(answer.explanation)
    for chunk in answer.evidence:
        typer.echo(f"  source: {chunk.citation}")
    typer.echo(f"Citation check: {answer.verification}")
    if answer.note:
        typer.echo(f"Note: {answer.note}")
    typer.echo("Draft only: a person must review this before it is sent.")
