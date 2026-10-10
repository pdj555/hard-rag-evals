"""Unanswerable: the only correct answer is no answer.

The corpus contains nothing relevant to the query. Any response, however
hedged, is a hallucination. Passing requires the agent to abstain. Most
RAG systems never abstain because nothing in their training rewards it.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    return _build_case(
        case_id="unanswerable-01",
        mode="unanswerable",
        name="unanswerable",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
    )
