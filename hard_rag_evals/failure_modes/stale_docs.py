"""Stale documents: recency must beat keyword overlap.

Documentation rots. The old page is longer, better written, and ranks
higher on every lexical signal, while the two sentence update that
supersedes it barely registers. Passing requires citing the current
document and never citing the stale one.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


_BUDGET = RetrievalBudget(max_docs=5, max_chars=8000)


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    case_id = f"stale-{difficulty}"
    return _build_case(
        case_id=case_id,
        mode="stale_docs",
        name=f"stale_docs{suffix}",
        budget=_BUDGET,
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
