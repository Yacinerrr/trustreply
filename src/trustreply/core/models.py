from __future__ import annotations

from typing import Literal

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


Verdict = Literal["yes", "no", "partial", "not_applicable", "gap"]
Confidence = Literal["high", "medium", "low"]
Verification = Literal["supported", "weak", "unsupported", "unchecked"]


class Answer(BaseModel):
    """A drafted answer to one question. Never final: a person reviews it before export."""

    question_id: str
    verdict: Verdict  # "gap" means we could not honestly answer from the policies
    explanation: str
    evidence: list[Chunk] = []  # the policy passages that back the answer
    confidence: Confidence = "low"
    verification: Verification = "unchecked"  # did a second check confirm the citations?
    note: str | None = None  # why this is a gap, or other reviewer-facing remarks

    @property
    def citations(self) -> list[str]:
        """Human-readable citations for the evidence, e.g. ['policy.md, section Access']."""
        return [chunk.citation for chunk in self.evidence]

    @property
    def is_gap(self) -> bool:
        return self.verdict == "gap"
