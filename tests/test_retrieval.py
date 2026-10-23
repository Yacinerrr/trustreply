from pathlib import Path

import pytest
from typer.testing import CliRunner

from trustreply.cli.main import app
from trustreply.core import Chunk, PolicyIndex, ingest_path
from trustreply.core.retrieval import _stem, tokenize


@pytest.fixture
def index(policies_dir: Path) -> PolicyIndex:
    return PolicyIndex(ingest_path(policies_dir))


def top_text(index: PolicyIndex, question: str) -> str:
    hits = index.search(question, top_k=1)
    assert hits, f"no evidence found for: {question}"
    return hits[0].chunk.text


def test_finds_mfa_evidence(index: PolicyIndex) -> None:
    assert "multi-factor" in top_text(index, "Do you enforce MFA for all employees?")


def test_finds_encryption_at_rest(index: PolicyIndex) -> None:
    assert "AES-256" in top_text(index, "Is customer data encrypted at rest?")


def test_finds_encryption_in_transit(index: PolicyIndex) -> None:
    assert "TLS" in top_text(index, "Is data encrypted in transit?")


def test_finds_access_reviews(index: PolicyIndex) -> None:
    assert "review user access" in top_text(index, "How often are user access rights reviewed?")


def test_finds_backups(index: PolicyIndex) -> None:
    assert "Backups" in top_text(index, "Do you perform regular backups and test restores?")


def test_unrelated_question_returns_no_evidence(index: PolicyIndex) -> None:
    assert index.search("Do you run a public bug bounty programme?") == []


def test_hits_carry_citation_metadata(index: PolicyIndex) -> None:
    hit = index.search("password length requirements", top_k=1)[0]
    assert hit.chunk.source == "access-control-policy.md"
    assert hit.chunk.section == "Authentication"
    assert hit.score > 0


def test_results_are_ranked_and_limited(index: PolicyIndex) -> None:
    hits = index.search("customer data access", top_k=2)
    assert len(hits) <= 2
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_empty_index_and_empty_query(index: PolicyIndex) -> None:
    assert PolicyIndex([]).search("anything") == []
    assert index.search("") == []
    assert index.search("the and of") == []  # only stopwords


def test_common_terms_in_every_chunk_still_score() -> None:
    chunks = [
        Chunk(id=f"p#{i}", text=f"We encrypt data in system {i}.", source="p.txt") for i in range(2)
    ]
    assert len(PolicyIndex(chunks).search("do you encrypt data")) == 2


def test_section_heading_is_searchable() -> None:
    chunk = Chunk(id="a#1", text="Reviewed every quarter.", source="a.md", section="Vendor Risk")
    assert PolicyIndex([chunk]).search("vendor risk")


@pytest.mark.parametrize(
    "words",
    [
        ["encrypt", "encrypted", "encryption"],
        ["authenticate", "authenticated", "authentication"],
        ["review", "reviews", "reviewed"],
        ["log", "logs", "logged", "logging"],
        ["policy", "policies"],
        ["access", "accessed"],
    ],
)
def test_stemmer_groups_word_forms(words: list[str]) -> None:
    assert len({_stem(w) for w in words}) == 1


def test_synonyms_expand_queries_only() -> None:
    assert "factor" in tokenize("MFA", expand=True)
    assert tokenize("MFA") == ["mfa"]


def test_cli_search_command(policies_dir: Path) -> None:
    runner = CliRunner()
    found = runner.invoke(app, ["search", str(policies_dir), "Is data encrypted at rest?"])
    assert found.exit_code == 0
    assert "data-protection.txt" in found.stdout
    missing = runner.invoke(app, ["search", str(policies_dir), "Do you run a bug bounty?"])
    assert "gap" in missing.stdout
    assert runner.invoke(app, ["search", str(policies_dir / "nope"), "x"]).exit_code == 1
