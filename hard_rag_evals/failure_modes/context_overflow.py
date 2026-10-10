"""Context overflow: a tight budget against a noisy corpus.

Ten documents, a budget for three, and eight distractors engineered for
keyword overlap. The two substantive documents must outrank the noise.
This is the retriever prioritization test: term frequency alone fails it.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    return _build_case(
        case_id="overflow-01",
        mode="context_overflow",
        name="context_overflow",
        budget=RetrievalBudget(max_docs=3, max_chars=2000),
    )
