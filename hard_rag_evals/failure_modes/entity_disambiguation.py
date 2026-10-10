"""Entity disambiguation: two people share a name, only one is the answer.

The corpus contains documents about different people with the same name.
The query carries a disambiguating detail (a role, a project). Passing
requires citing the right person's document and never the wrong one's.
Hard stuffs the wrong document with query terms so lexical ranking
prefers it: only the role appositive disambiguates.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    return _build_case(
        case_id=f"disambiguation-{difficulty}",
        mode="entity_disambiguation",
        name=f"entity_disambiguation{suffix}",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
