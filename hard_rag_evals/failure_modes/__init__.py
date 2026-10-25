"""Failure mode eval cases. Each module builds one EvalCase from its fixture.

A failure mode is a specific way RAG systems break in production that
standard benchmarks do not isolate. The suite treats each mode as a
separate, gradeable behavior so a team can see exactly which failure
their system still has.
"""
from __future__ import annotations

import json
from importlib import resources

from ..types import Corpus, Document, EvalCase, RetrievalBudget

_FIXTURE_DIR = resources.files(__package__).joinpath("../fixtures")


def _load_fixture(name: str) -> dict:
    path = _FIXTURE_DIR.joinpath(f"{name}.json")
    return json.loads(path.read_text())


def _build_case(
    case_id: str,
    mode: str,
    name: str,
    budget: RetrievalBudget,
    difficulty: str = "medium",
) -> EvalCase:
    f = _load_fixture(name)
    corpus = Corpus(
        documents=tuple(
            Document(
                id=d["id"],
                text=d["text"],
                source=d["source"],
                published=d["published"],
            )
            for d in f["documents"]
        )
    )
    pair = f.get("conflict_pair")
    return EvalCase(
        id=case_id,
        mode=mode,
        query=f["query"],
        corpus=corpus,
        budget=budget,
        gold_doc_ids=tuple(f.get("gold_doc_ids", [])),
        must_cite=tuple(f.get("must_cite", [])),
        must_not_cite=tuple(f.get("must_not_cite", [])),
        should_abstain=bool(f.get("should_abstain", False)),
        conflict_pair=tuple(pair) if pair else None,
        expected=f.get("expected", ""),
        difficulty=difficulty,
        numeric_expected=f.get("numeric_expected"),
        numeric_tolerance=float(f.get("numeric_tolerance", 0.0)),
        order_check=(
            (tuple(f["order_check"][0]), tuple(f["order_check"][1]))
            if f.get("order_check")
            else None
        ),
        forbidden_phrases=tuple(f.get("forbidden_phrases", [])),
    )


from . import (  # noqa: E402
    adversarial,
    citation_fabrication,
    compositional,
    context_overflow,
    contradictory_sources,
    entity_disambiguation,
    instruction_hierarchy,
    long_context_needle,
    multi_hop,
    numeric_aggregation,
    retrieval_misses,
    retrieval_self_report,
    stale_docs,
    temporal_reasoning,
    unanswerable,
)

_TIERED = (
    contradictory_sources,
    stale_docs,
    retrieval_misses,
    citation_fabrication,
    multi_hop,
    context_overflow,
    unanswerable,
    temporal_reasoning,
    numeric_aggregation,
    entity_disambiguation,
    instruction_hierarchy,
    long_context_needle,
    retrieval_self_report,
)

# 13 tiered modes x easy/medium/hard, plus adversarial (hard, brutal) and
# compositional (4 brutal): 45 cases.
ALL_CASES: list[EvalCase] = (
    [m.build_easy() for m in _TIERED]
    + [m.build() for m in _TIERED]
    + [m.build_hard() for m in _TIERED]
    + adversarial.build_all()
    + compositional.build_all()
)
