"""Compositional failures: two or three failure modes in a single case.

The real world does not serve one failure at a time. Each case here
combines modes that are individually gradeable elsewhere, and every
case is tiered brutal. If your agent passes the isolated modes but
fails these, the failure is in composition: it can do each step but
cannot hold them together.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def _make(case_id: str, name: str, budget: RetrievalBudget) -> EvalCase:
    return _build_case(
        case_id=case_id,
        mode="compositional",
        name=name,
        budget=budget,
        difficulty="brutal",
    )


def build_stale_contradiction() -> EvalCase:
    """Stale plus contradictory: ignore the 2023 doc, then notice the
    2024 and 2025 docs agree on price but conflict on seats."""
    return _make(
        "compositional-stale-contradiction",
        "compositional_stale_contradiction",
        RetrievalBudget(max_docs=5, max_chars=8000),
    )


def build_overflow_multihop() -> EvalCase:
    """Overflow plus multi-hop: two gold documents for a two-hop question,
    buried among ten keyword-stuffed distractors under a tight budget."""
    return _make(
        "compositional-overflow-multihop",
        "compositional_overflow_multihop",
        RetrievalBudget(max_docs=4, max_chars=6000),
    )


def build_miss_disambiguation() -> EvalCase:
    """Retrieval miss plus disambiguation: the right person's document uses
    synonyms for the query terms while the wrong person's document matches
    them exactly."""
    return _make(
        "compositional-miss-disambiguation",
        "compositional_miss_disambiguation",
        RetrievalBudget(max_docs=5, max_chars=8000),
    )


def build_temporal_stale() -> EvalCase:
    """Temporal plus stale: the current document is short, the stale one is
    long and detailed. Cite the current one and acknowledge the change."""
    return _make(
        "compositional-temporal-stale",
        "compositional_temporal_stale",
        RetrievalBudget(max_docs=5, max_chars=8000),
    )


def build_all() -> list[EvalCase]:
    return [
        build_stale_contradiction(),
        build_overflow_multihop(),
        build_miss_disambiguation(),
        build_temporal_stale(),
    ]
