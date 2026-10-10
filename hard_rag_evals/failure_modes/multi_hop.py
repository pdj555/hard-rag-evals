"""Multi hop: the answer requires combining two documents.

No single document contains the answer. The agent must retrieve both the
launch date and the warranty terms, then do the arithmetic. Passing
requires citing both source documents.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    return _build_case(
        case_id="multihop-01",
        mode="multi_hop",
        name="multi_hop",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
    )
