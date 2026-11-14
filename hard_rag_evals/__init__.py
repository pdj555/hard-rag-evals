"""hard-rag-evals: failure mode evals for agentic RAG."""
from .runner import (
    DIFFICULTY_ORDER,
    GATES,
    gate_breakdown,
    grade,
    order_spread,
    permute_documents,
    render_markdown,
    run_suite,
    summary_by_difficulty,
    summary_by_mode,
)
from .types import Agent, Answer, Corpus, Document, EvalCase, EvalResult, RetrievalBudget

__all__ = [
    "DIFFICULTY_ORDER",
    "GATES",
    "Agent",
    "Answer",
    "Corpus",
    "Document",
    "EvalCase",
    "EvalResult",
    "RetrievalBudget",
    "gate_breakdown",
    "grade",
    "order_spread",
    "permute_documents",
    "render_markdown",
    "run_suite",
    "summary_by_difficulty",
    "summary_by_mode",
]
