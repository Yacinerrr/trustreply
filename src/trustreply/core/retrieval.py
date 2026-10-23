"""Find the policy chunks most relevant to a question (BM25 keyword search).

This is the evidence-gathering step: the answer-drafting step may only use what this
returns, so every answer can be traced back to real policy text. We use plain BM25 with
light stemming and a few security synonyms. Embeddings can be added later if the
evaluation (Phase 3) shows they help.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from pydantic import BaseModel

from trustreply.core.models import Chunk

# BM25 parameters (standard defaults).
K1 = 1.5
B = 0.75
MIN_MATCHED_TERMS = 2  # distinct query words a chunk must contain (for longer questions)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """a an and are as at be been by can could do does for from had has have how if in
    into is it its of on or our shall should so than that the their them then there these
    they this to us was we were what when where which who will with would you your any all
    each per""".split()
)

# Security shorthand customers and policies use interchangeably. Applied to the query only.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "mfa": ("multi", "factor", "authentication"),
    "2fa": ("multi", "factor", "authentication"),
    "multifactor": ("multi", "factor", "authentication"),
    "sso": ("single", "sign", "authentication"),
    "pentest": ("penetration", "test"),
    "pentests": ("penetration", "test"),
    "pen": ("penetration",),
    "dr": ("disaster", "recovery"),
    "bcp": ("business", "continuity"),
    "ir": ("incident", "response"),
    "vpn": ("virtual", "private", "network"),
    "pii": ("personal", "data"),
    "gdpr": ("personal", "data", "privacy"),
    "sdlc": ("secure", "development", "lifecycle"),
    "iam": ("identity", "access"),
    "rbac": ("role", "access"),
    "edr": ("endpoint", "detection"),
    "siem": ("log", "monitoring"),
    "tls": ("encryption", "transit"),
    "ssl": ("encryption", "transit"),
    "encrypt": ("encryption",),
    "backup": ("backups",),
    "length": ("long", "characters"),
    "offboarding": ("leave", "terminated", "disabled"),
    "onboarding": ("new", "hire"),
    "vendor": ("supplier", "third", "party"),
    "supplier": ("vendor", "third", "party"),
    "subcontractor": ("vendor", "third", "party"),
}

_SUFFIXES = ("ments", "ment", "ings", "ing", "ions", "ion", "ed", "es", "ly", "s")
_MIN_STEM = 3


def _stem(word: str) -> str:
    """Light stemming so 'encrypted', 'encrypts' and 'encryption' share one form.

    Deliberately simple and predictable: strip one common suffix, drop a trailing 'e',
    and undo a doubled consonant ('logging' -> 'log'). It only has to make a question and
    a policy agree on a word, not be linguistically perfect.
    """
    if word.isdigit() or len(word) <= _MIN_STEM:
        return word
    if word.endswith(("ies", "ied")) and len(word) - 3 >= _MIN_STEM:
        return word[:-3] + "y"  # policies -> policy
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            if suffix == "s" and word.endswith("ss"):  # access, not "acces"
                break
            word = word[: -len(suffix)]
            if suffix in ("ing", "ed") and word[-1] == word[-2] and word[-1] not in "lsz":
                word = word[:-1]  # logging -> logg -> log
            break
    if word.endswith("e") and len(word) > _MIN_STEM + 1:
        word = word[:-1]
    return word


def tokenize(text: str, *, expand: bool = False) -> list[str]:
    """Lowercase, drop stopwords, stem. With expand=True, add synonyms (for queries)."""
    raw = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]
    if expand:
        extra: list[str] = []
        for token in raw:
            extra.extend(_SYNONYMS.get(token, ()))
        raw.extend(t for t in extra if t not in _STOPWORDS)
    return [_stem(t) for t in raw]


class Hit(BaseModel):
    """A retrieved chunk and how well it matched."""

    chunk: Chunk
    score: float


class PolicyIndex:
    """A searchable index over policy chunks."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._tokens = [tokenize(c.text + " " + (c.section or "")) for c in chunks]
        self._tf = [Counter(tokens) for tokens in self._tokens]
        self._lengths = [len(tokens) for tokens in self._tokens]
        total = sum(self._lengths)
        self._avg_len = (total / len(chunks)) if chunks else 0.0

        document_frequency: Counter[str] = Counter()
        for tf in self._tf:
            document_frequency.update(tf.keys())
        n = len(chunks)
        # Always-positive idf (BM25+ style) so terms found in many chunks still count.
        self._idf = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> list[Hit]:
        """Return up to top_k chunks ranked by relevance, best first.

        A chunk only counts as evidence if it matches enough of the question: one shared word
        is enough for a one- or two-word query, but longer questions need at least two
        distinct matching words. This stops a single generic word ("run", "data") from
        passing off an unrelated paragraph as evidence. An empty result means "no evidence
        found", and the caller should report a gap instead of guessing.
        """
        query_terms = list(dict.fromkeys(tokenize(query, expand=True)))
        if not query_terms or not self.chunks:
            return []
        required_matches = 1 if len(query_terms) <= 2 else MIN_MATCHED_TERMS

        scores: list[tuple[float, int]] = []
        for index, tf in enumerate(self._tf):
            length_norm = 1 - B + B * (self._lengths[index] / self._avg_len if self._avg_len else 1)
            score = 0.0
            matched = 0
            for term in query_terms:
                frequency = tf.get(term, 0)
                if frequency:
                    matched += 1
                    score += self._idf[term] * (
                        frequency * (K1 + 1) / (frequency + K1 * length_norm)
                    )
            if matched >= required_matches and score > min_score:
                scores.append((score, index))

        scores.sort(key=lambda pair: (-pair[0], pair[1]))  # ties keep document order
        return [Hit(chunk=self.chunks[i], score=round(s, 4)) for s, i in scores[:top_k]]
