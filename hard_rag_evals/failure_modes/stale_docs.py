"""Stale documents: recency must beat keyword overlap.

Documentation rots. The old page is longer, better written, and ranks
higher on every lexical signal, while the two sentence update that
supersedes it barely registers. Passing requires citing the current
document and never citing the stale one.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def build() -> EvalCase:
    return _build_case(
        case_id="stale-01",
        mode="stale_docs",
        name="stale_docs",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
    )
