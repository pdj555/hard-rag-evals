"""Retrieval misses: the answer exists but vocabulary mismatch hides it.

The document says "automobiles", the user asks about "cars", and a
lexical retriever returns nothing useful. This case isolates retriever
recall from answer quality: the gold document is scored purely on
whether it was retrieved at all.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    # Tight budget on purpose: the gold document ranks below the two
    # distractors on lexical overlap, so it is never retrieved at all.
    return _build_case(
        case_id="retrieval-miss-01",
        mode="retrieval_misses",
        name="retrieval_misses",
        budget=RetrievalBudget(max_docs=2, max_chars=8000),
    )
