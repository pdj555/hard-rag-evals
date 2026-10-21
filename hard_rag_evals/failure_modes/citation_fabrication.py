"""Citation fabrication: every citation must name a real document.

Models invent plausible document ids. The answer can read perfectly while
pointing at nothing. The grader checks each citation against the corpus,
so a fabricated id fails even when the surrounding text is correct.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


_BUDGET = RetrievalBudget(max_docs=5, max_chars=8000)


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    case_id = f"fabrication-{difficulty}"
    return _build_case(
        case_id=case_id,
        mode="citation_fabrication",
        name=f"citation_fabrication{suffix}",
        budget=_BUDGET,
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
