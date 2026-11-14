"""hard-rag-evals: failure mode evals for agentic RAG."""
from .failure_modes import DATASET_VERSION
from .provenance import CANARY, GRADER_VERSION
from .runner import (
    DEFAULT_SHUFFLE_SEED,
    DIFFICULTY_ORDER,
    GATES,
    gate_breakdown,
    grade,
    order_spread,
    permute_documents,
    refusal_summary,
    render_markdown,
    run_suite,
    summary_by_difficulty,
    summary_by_mode,
)
from .types import Agent, Answer, Corpus, Document, EvalCase, EvalResult, RetrievalBudget

__all__ = [
    "DEFAULT_SHUFFLE_SEED",
    "CANARY",
    "DATASET_VERSION",
    "GRADER_VERSION",
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
    "refusal_summary",
    "render_markdown",
    "run_suite",
    "summary_by_difficulty",
    "summary_by_mode",
]
