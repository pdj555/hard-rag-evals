"""Core types for hard-rag-evals.

Every eval case, agent answer, and result flows through these types.
Keeping them small and explicit is deliberate: the suite grades behavior,
not implementation, so the contract between harness and agent stays thin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Document:
    """One retrievable unit. Published date is load bearing: several
    failure modes hinge on the agent reasoning about recency."""

    id: str
    text: str
    source: str
    published: str  # ISO date, YYYY-MM-DD


@dataclass(frozen=True)
class Corpus:
    documents: tuple[Document, ...]

    def by_id(self, doc_id: str) -> Document | None:
        for d in self.documents:
            if d.id == doc_id:
                return d
        return None

    @property
    def ids(self) -> set[str]:
        return {d.id for d in self.documents}


@dataclass(frozen=True)
class RetrievalBudget:
    """Hard caps the agent must respect. Context overflow cases set these
    tight on purpose."""

    max_docs: int = 5
    max_chars: int = 8000


@dataclass
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)
    retrieved_ids: list[str] = field(default_factory=list)
    abstained: bool = False


class Agent(Protocol):
    """The only contract an agent must satisfy. Name is used in reports."""

    name: str

    def answer(
        self, query: str, corpus: Corpus, budget: RetrievalBudget
    ) -> Answer: ...


@dataclass(frozen=True)
class EvalCase:
    id: str
    mode: str
    query: str
    corpus: Corpus
    budget: RetrievalBudget
    gold_doc_ids: tuple[str, ...] = ()
    must_cite: tuple[str, ...] = ()
    must_not_cite: tuple[str, ...] = ()
    should_abstain: bool = False
    conflict_pair: tuple[str, str] | None = None
    expected: str = ""
    difficulty: str = "medium"  # easy, medium, hard, or brutal
    numeric_expected: float | None = None
    numeric_tolerance: float = 0.0
    order_check: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    forbidden_phrases: tuple[str, ...] = ()


@dataclass
class EvalResult:
    case_id: str
    mode: str
    passed: bool
    scores: dict[str, float]
    notes: list[str]
    difficulty: str = "medium"
