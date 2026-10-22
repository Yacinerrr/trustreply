"""Turn policy documents (PDF, DOCX, Markdown, TXT) into citable text chunks."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from trustreply.core.models import Chunk

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt"}
DEFAULT_MAX_CHARS = 800

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


class UnsupportedFileError(ValueError):
    """Raised when a file type is not one we can ingest."""


# A "block" is (page, section, text) before it is split into chunks.
_Block = tuple[int | None, str | None, str]


def _read_pdf(path: Path) -> Iterator[_Block]:
    reader = PdfReader(str(path))
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            yield number, None, text


def _read_docx(path: Path) -> Iterator[_Block]:
    doc = Document(str(path))
    section: str | None = None
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name or "") if paragraph.style is not None else ""
        if style.lower().startswith("heading") or style.lower() == "title":
            section = text
            continue
        yield None, section, text


def _read_markdown(path: Path) -> Iterator[_Block]:
    section: str | None = None
    buffer: list[str] = []

    def flush() -> Iterator[_Block]:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if text:
            yield None, section, text

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _HEADING_RE.match(line)
        if match:
            yield from flush()
            section = match.group(1).strip()
        elif not line.strip():
            yield from flush()
        else:
            buffer.append(line)
    yield from flush()


def _read_text(path: Path) -> Iterator[_Block]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    for paragraph in re.split(r"\n\s*\n", raw):
        text = paragraph.strip()
        if text:
            yield None, None, text


_READERS = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".md": _read_markdown,
    ".markdown": _read_markdown,
    ".txt": _read_text,
}


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split text longer than max_chars on sentence boundaries, then hard-wrap."""
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        while len(sentence) > max_chars:  # a single enormous sentence
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _chunk_blocks(blocks: Iterator[_Block], source: str, max_chars: int) -> Iterator[Chunk]:
    """Merge small neighbouring blocks (same page and section) up to max_chars."""
    index = 0
    pending: tuple[int | None, str | None, str] | None = None

    def make(page: int | None, section: str | None, text: str) -> Chunk:
        nonlocal index
        index += 1
        return Chunk(id=f"{source}#{index}", text=text, source=source, page=page, section=section)

    for page, section, text in blocks:
        for piece in _split_long(text, max_chars):
            if (
                pending
                and pending[:2] == (page, section)
                and (len(pending[2]) + 2 + len(piece) <= max_chars)
            ):
                pending = (page, section, f"{pending[2]}\n\n{piece}")
                continue
            if pending:
                yield make(*pending)
            pending = (page, section, piece)
    if pending:
        yield make(*pending)


def ingest_file(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Extract citable chunks from a single policy file."""
    path = Path(path)
    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        raise UnsupportedFileError(
            f"Unsupported file type '{suffix}' for {path.name}. "
            f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    return list(_chunk_blocks(reader(path), path.name, max_chars))


def ingest_path(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Ingest one file, or every supported file inside a folder (recursively).

    Unsupported files in a folder are skipped; an unsupported single file raises.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file or folder: {path}")
    if path.is_file():
        return ingest_file(path, max_chars)
    chunks: list[Chunk] = []
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        if file.suffix.lower() in SUPPORTED_SUFFIXES:
            chunks.extend(ingest_file(file, max_chars))
    return chunks
