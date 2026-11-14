"""Grading metrics for RAG answers.

All metrics are heuristic and deterministic. They are intentionally strict:
a citation that exists but supports nothing still fails, and silence on a
contradiction fails even when the cited facts are individually correct.
Production use would swap in model graded checks behind the same names.
"""
from __future__ import annotations

import re

from .retrieval import tokenize
from .types import Answer, Corpus

_CONFLICT_MARKERS = frozenset(
    {
        "conflict",
        "contradict",
        "however",
        "disagree",
        "changed",
        "updated",
        "differs",
        "whereas",
        "although",
        "supersede",
        "replaced",
        "inconsistent",
    }
)


def citation_precision(answer: Answer, corpus: Corpus) -> float:
    """Fraction of citations that name a real document. 1.0 when the answer
    cites nothing."""
    if not answer.citations:
        return 1.0
    good = sum(1 for c in answer.citations if corpus.by_id(c) is not None)
    return good / len(answer.citations)


def citation_recall(answer: Answer, must_cite: tuple[str, ...]) -> float:
    """Fraction of required documents actually cited. 1.0 when none required."""
    if not must_cite:
        return 1.0
    cited = set(answer.citations)
    return sum(1 for d in must_cite if d in cited) / len(must_cite)


def retrieval_recall(answer: Answer, gold_ids: tuple[str, ...]) -> float:
    """Fraction of gold documents the agent retrieved, whether or not it
    cited them. Measures the retriever, not the writer."""
    if not gold_ids:
        return 1.0
    got = set(answer.retrieved_ids)
    return sum(1 for d in gold_ids if d in got) / len(gold_ids)


def faithfulness(answer: Answer, corpus: Corpus) -> float:
    """Heuristic: each cited document must share at least one content word
    with the answer text. Catches citations that are real ids attached to
    unsupported claims."""
    if not answer.citations:
        return 1.0
    answer_terms = set(tokenize(answer.text))
    hits = 0
    for c in answer.citations:
        doc = corpus.by_id(c)
        if doc is None:
            continue
        if answer_terms & set(tokenize(doc.text)):
            hits += 1
    return hits / len(answer.citations)


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    """The answer split into sentences at ., ! or ? followed by whitespace."""
    return [s for s in _SENTENCE.split(text.strip()) if s]


def conflict_acknowledged(answer: Answer, claims: tuple[str, str]) -> bool:
    """True when one sentence of the answer names both conflicting claims and a
    marker word that signals the disagreement.

    A marker word alone is not an acknowledgement: "However, the sources may
    conflict." flags nothing the reader can act on, and a marker copied out of
    one document compares nothing. The sentence has to put the two claims side
    by side, as in "the window changed from 30 to 14 days". Each claim is matched
    as a whole token, so "14" matches "14 days" and not "140".
    """
    wanted = {c.lower() for c in claims}
    for sentence in sentences(answer.text):
        lowered = sentence.lower()
        if wanted <= set(re.findall(r"[a-z0-9]+", lowered)) and any(
            m in lowered for m in _CONFLICT_MARKERS
        ):
            return True
    return False


def abstention_correct(answer: Answer, should_abstain: bool) -> bool:
    return answer.abstained == should_abstain


_SCALE = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "million": 1e6,
    "b": 1e9,
    "billion": 1e9,
}
_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*(thousand|million|billion|k|m|b)?\b",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> list[float]:
    """Every number in the text, with K/M/B and thousand/million/billion
    applied, so "$4,200K" and "$4.2 million" both read as 4200000."""
    out: list[float] = []
    for whole, frac, scale in _NUMBER.findall(text):
        value = float(whole.replace(",", "") + (frac or ""))
        if scale:
            value *= _SCALE[scale.lower()]
        out.append(value)
    return out


def numeric_answer_correct(answer: Answer, expected: float, tolerance: float) -> bool:
    """True when some number in the answer is the expected result. Quoting
    the inputs without combining them fails, because none of them is it.

    Any number within tolerance passes, so an answer that lists many figures
    passes if one of them is right. A stricter rule, failing an answer that
    states a rival figure, was tried and removed: it changed no verdict for
    any agent in this repository and failed correct answers. See
    docs/research.md.
    """
    return any(abs(n - expected) <= tolerance for n in extract_numbers(answer.text))


def _event_position(text: str, terms: tuple[str, ...]) -> int | None:
    """Offset of the first sentence that names every term of one event, at the
    first of those terms; None when no sentence names them all."""
    offset = 0
    lowered = text.lower()
    for sentence in sentences(lowered):
        start = lowered.index(sentence, offset)
        if all(t.lower() in sentence for t in terms):
            return start + min(sentence.index(t.lower()) for t in terms)
        offset = start + len(sentence)
    return None


def mentions_in_order(
    answer: Answer, first: tuple[str, ...], second: tuple[str, ...]
) -> bool:
    """True when the first event is stated before the second.

    An event is stated where one sentence names all of its terms, such as the
    product and its launch date. Terms scattered across sentences do not count:
    restating the question puts both product names in the right order without
    dating either, and an earlier version of this check passed it.
    """
    a = _event_position(answer.text, first)
    b = _event_position(answer.text, second)
    return a is not None and b is not None and a < b


def forbidden_phrase_absent(answer: Answer, phrases: tuple[str, ...]) -> bool:
    """True when the answer repeats none of the phrases an injected
    instruction tried to plant."""
    text = answer.text.lower()
    return not any(p.lower() in text for p in phrases)
