from pathlib import Path

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from trustreply.cli.main import app
from trustreply.core import parse_questionnaire
from trustreply.core.questionnaire import QuestionnaireFormatError


def test_detects_header_row_and_columns(questionnaire_xlsx: Path) -> None:
    result = parse_questionnaire(questionnaire_xlsx)
    assert result.source == "acme-security-review.xlsx"
    assert result.answer_column_exists is True
    assert [q.row for q in result.questions] == [4, 5, 7]  # blank and too-short rows skipped
    first = result.questions[0]
    assert first.id == "Security!B4"
    assert first.question_col == "B"
    assert first.answer_col == "C"
    assert first.answer_cell == "C4"
    assert first.reference == "AC-1"
    assert "multi-factor" in first.text


def test_sheets_without_questions_are_skipped(questionnaire_xlsx: Path) -> None:
    result = parse_questionnaire(questionnaire_xlsx)
    assert {q.sheet for q in result.questions} == {"Security"}


def test_sheet_option(questionnaire_xlsx: Path) -> None:
    assert len(parse_questionnaire(questionnaire_xlsx, sheet="Security").questions) == 3
    with pytest.raises(QuestionnaireFormatError, match="not found"):
        parse_questionnaire(questionnaire_xlsx, sheet="Missing")


def test_csv_without_answer_column_picks_a_new_one(questionnaire_no_answer_col: Path) -> None:
    result = parse_questionnaire(questionnaire_no_answer_col)
    assert result.answer_column_exists is False
    assert [q.id for q in result.questions] == ["A2", "A3"]
    assert {q.answer_col for q in result.questions} == {"C"}  # after the existing two columns
    assert result.questions[0].sheet is None


def test_explicit_columns_override_detection(tmp_path: Path) -> None:
    path = tmp_path / "odd.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Check", "Result"])  # no recognisable headers
    ws.append(["1", "Is there a documented backup policy?", None])
    wb.save(str(path))

    with pytest.raises(QuestionnaireFormatError, match="--question-col"):
        parse_questionnaire(path)

    result = parse_questionnaire(path, question_col="B", answer_col="C")
    assert len(result.questions) == 1
    assert result.questions[0].answer_cell == "C2"


def test_invalid_column_letter(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("Question\nDo you encrypt data?\n", encoding="utf-8")
    with pytest.raises(QuestionnaireFormatError, match="not a valid column"):
        parse_questionnaire(path, question_col="1!")


def test_unsupported_and_missing_files(tmp_path: Path) -> None:
    bad = tmp_path / "q.pdf"
    bad.write_bytes(b"x")
    with pytest.raises(QuestionnaireFormatError, match="Unsupported"):
        parse_questionnaire(bad)
    with pytest.raises(FileNotFoundError):
        parse_questionnaire(tmp_path / "nope.xlsx")


def test_semicolon_csv(tmp_path: Path) -> None:
    path = tmp_path / "eu.csv"
    path.write_text("Question;Answer\nDo you log admin actions?;\n", encoding="utf-8")
    result = parse_questionnaire(path)
    assert result.answer_column_exists is True
    assert result.questions[0].answer_cell == "B2"


def test_cli_questions_command(questionnaire_xlsx: Path) -> None:
    result = CliRunner().invoke(app, ["questions", str(questionnaire_xlsx)])
    assert result.exit_code == 0
    assert "Found 3 questions" in result.stdout
    assert "Security!B4 -> C4" in result.stdout


def test_cli_questions_error(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["questions", str(tmp_path / "missing.xlsx")])
    assert result.exit_code == 1
