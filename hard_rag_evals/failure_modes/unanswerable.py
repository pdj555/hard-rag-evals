"""Unanswerable queries: the corpus contains nothing relevant.

The only correct behavior is abstention. Easy uses an obviously
unrelated corpus; hard uses near-miss documents that tempt the agent
into stitching an answer from almost-relevant parts.

Tiers: easy shows the behavior in its simplest form, medium is the
original case, hard pushes it to where production systems break.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    return _build_case(
        case_id=f"unanswerable-{difficulty}",
        mode="unanswerable",
        name=f"unanswerable{suffix}",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
