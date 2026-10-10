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


def _build_case(case_id: str, mode: str, name: str, budget: RetrievalBudget) -> EvalCase:
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
    )


from . import (  # noqa: E402
    citation_fabrication,
    context_overflow,
    contradictory_sources,
    multi_hop,
    retrieval_misses,
    stale_docs,
    unanswerable,
)

ALL_CASES: list[EvalCase] = [
    contradictory_sources.build(),
    stale_docs.build(),
    retrieval_misses.build(),
    citation_fabrication.build(),
    multi_hop.build(),
    context_overflow.build(),
    unanswerable.build(),
]
