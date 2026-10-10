"""Numeric aggregation: the answer is a computation over several documents.

Quoting the inputs is not enough. Easy sums two quarters, medium averages
three, hard mixes units ($4,200K vs $5.8M) and plants a distractor with
last year's number. The grader normalizes $, commas, and K/M/B suffixes,
so "$10 million" and "10000000" both count.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    return _build_case(
        case_id=f"numeric-{difficulty}",
        mode="numeric_aggregation",
        name=f"numeric_aggregation{suffix}",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
