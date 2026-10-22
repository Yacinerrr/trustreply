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
