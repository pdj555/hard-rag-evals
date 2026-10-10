"""Temporal reasoning: events have dates, and the agent must order them.

Easy: two dated events, "which happened first?" The wrong order wins
lexical ties by document id, so an agent that does not read dates fails.
Medium: a rumor document mentions an earlier date for an event that
actually happened later; it must not be treated as a launch.
Hard: the document published later describes the earlier event. Event
dates beat published dates; an agent that sorts by recency gets it
backwards.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    return _build_case(
        case_id=f"temporal-{difficulty}",
        mode="temporal_reasoning",
        name=f"temporal_reasoning{suffix}",
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
