"""Adversarial corpus: documents designed to trick retrieval.

Not noise, but traps: keyword-stuffed titles on content that answers
nothing, near-duplicate documents that answer a slightly different
question, and version histories where only date reasoning picks the
current truth. Hard tests whether the agent sees through the tricks;
brutal gives it three versions of the same fact and a document that
quotes the wrong one.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build_hard() -> EvalCase:
    return _build_case(
        case_id="adversarial-hard",
        mode="adversarial_retrieval",
        name="adversarial_retrieval_hard",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
        difficulty="hard",
    )


def build_brutal() -> EvalCase:
    return _build_case(
        case_id="adversarial-brutal",
        mode="adversarial_retrieval",
        name="adversarial_retrieval_brutal",
        budget=RetrievalBudget(max_docs=8, max_chars=12000),
        difficulty="brutal",
    )


def build_all() -> list[EvalCase]:
    return [build_hard(), build_brutal()]
