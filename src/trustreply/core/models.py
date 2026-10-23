from __future__ import annotations

from pydantic import BaseModel


class Chunk(BaseModel):
    """A piece of a policy document, with enough metadata to cite it exactly."""

    id: str
    text: str
    source: str  # file name, e.g. "access-control-policy.md"
    page: int | None = None  # 1-based; None for formats without pages
    section: str | None = None  # nearest heading, when known

    @property
    def citation(self) -> str:
        """Human-readable reference used in answers, e.g. 'policy.pdf, p. 3'."""
        parts = [self.source]
        if self.page is not None:
            parts.append(f"p. {self.page}")
        if self.section:
            parts.append(f"section '{self.section}'")
        return ", ".join(parts)


class Question(BaseModel):
    """One question found in a customer's questionnaire, with where its answer belongs."""

    id: str  # unique, e.g. "Sheet1!B5" (or "B5" for CSV)
    text: str
    sheet: str | None = None  # None for CSV
    row: int  # 1-based row of the question
    question_col: str  # column letter holding the question, e.g. "B"
    answer_col: str  # column letter where the answer should be written
    reference: str | None = None  # customer's own number, e.g. "AC-1.2"

    @property
    def answer_cell(self) -> str:
        """A1-style address of the cell to fill, e.g. 'C5'."""
        return f"{self.answer_col}{self.row}"


class Questionnaire(BaseModel):
    """All questions found in one questionnaire file."""

    source: str  # file name
    questions: list[Question]
    answer_column_exists: bool  # False when the file had no answer column and we picked one
