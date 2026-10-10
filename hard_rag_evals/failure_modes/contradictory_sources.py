"""Contradictory sources: two documents disagree and the agent must say so.

The classic production failure: the corpus contains both the old and new
version of a fact, the agent picks one silently, and the user acts on the
wrong one. Passing requires citing both documents AND signaling the
disagreement in the answer text.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    return _build_case(
        case_id="contradiction-01",
        mode="contradictory_sources",
        name="contradictory_sources",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
    )
