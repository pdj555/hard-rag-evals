"""Citation fabrication: every citation must name a real document.

Models invent plausible document ids. The answer can read perfectly while
pointing at nothing. The grader checks each citation against the corpus,
so a fabricated id fails even when the surrounding text is correct.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    return _build_case(
        case_id="fabrication-01",
        mode="citation_fabrication",
        name="citation_fabrication",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
    )
