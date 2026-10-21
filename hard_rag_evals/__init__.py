"""hard-rag-evals: failure mode evals for agentic RAG."""
from .runner import DIFFICULTY_ORDER, grade, render_markdown, run_suite, summary_by_difficulty
from .types import Agent, Answer, Corpus, Document, EvalCase, EvalResult, RetrievalBudget

__all__ = [
    "DIFFICULTY_ORDER",
    "Agent",
    "Answer",
    "Corpus",
    "Document",
    "EvalCase",
    "EvalResult",
    "RetrievalBudget",
    "grade",
    "render_markdown",
    "run_suite",
    "summary_by_difficulty",
]
