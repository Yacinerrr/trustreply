from pathlib import Path

import pytest

from trustreply.core import ingest_path
from trustreply.core.ingest import UnsupportedFileError, _split_long, ingest_file


def test_markdown_tracks_sections(policies_dir: Path) -> None:
    chunks = ingest_file(policies_dir / "access-control-policy.md")
    sections = {c.section for c in chunks}
    assert {"Authentication", "Access reviews", "Privileged access"} <= sections
    mfa = next(c for c in chunks if "multi-factor" in c.text)
    assert mfa.section == "Authentication"
    assert mfa.source == "access-control-policy.md"
    assert mfa.page is None
    assert "access-control-policy.md" in mfa.citation
    assert "Authentication" in mfa.citation


def test_txt_splits_on_paragraphs(policies_dir: Path) -> None:
    chunks = ingest_file(policies_dir / "data-protection.txt", max_chars=80)
    assert len(chunks) >= 3
    assert any("AES-256" in c.text for c in chunks)
    assert all(len(c.text) <= 80 for c in chunks)


def test_pdf_keeps_page_numbers(pdf_file: Path) -> None:
    chunks = ingest_file(pdf_file)
    assert [c.page for c in chunks] == [1, 2]
    assert "72 hours" in chunks[0].text
    assert "p. 2" in chunks[1].citation


def test_docx_uses_headings_as_sections(docx_file: Path) -> None:
    chunks = ingest_file(docx_file)
    by_section = {c.section: c.text for c in chunks}
    assert "security review" in by_section["Vendor Management"]
    assert "contract ends" in by_section["Offboarding"]


def test_folder_ingest_skips_unsupported(policies_dir: Path, tmp_path: Path) -> None:
    (tmp_path / "notes.exe").write_bytes(b"\x00\x01")
    (tmp_path / "a.md").write_text("# A\n\nHello world.", encoding="utf-8")
    assert [c.source for c in ingest_path(tmp_path)] == ["a.md"]
    assert {c.source for c in ingest_path(policies_dir)} == {
        "access-control-policy.md",
        "data-protection.txt",
    }


def test_chunk_ids_are_unique(policies_dir: Path) -> None:
    ids = [c.id for c in ingest_path(policies_dir)]
    assert len(ids) == len(set(ids))


def test_unsupported_single_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "x.exe"
    bad.write_bytes(b"x")
    with pytest.raises(UnsupportedFileError):
        ingest_path(bad)


def test_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_path(tmp_path / "nope")


def test_split_long_respects_limit() -> None:
    text = "First sentence here. " * 30 + "x" * 500
    pieces = _split_long(text, 100)
    assert all(len(p) <= 100 for p in pieces)
    assert "".join(pieces).replace(" ", "").startswith("Firstsentencehere.")
